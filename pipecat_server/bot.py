"""Pipecat bot for AI fitness coaching with Gemini Live."""

import asyncio
import json
from loguru import logger

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    TextFrame,
    EndFrame,
    StartFrame,
    LLMMessagesAppendFrame,
)
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContextFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.services.google.gemini_live import GeminiLiveLLMService
from pipecat.transports.services.daily import DailyTransport, DailyParams

from pipecat_server.config import config
from pipecat_server.prompts import get_fitness_coach_prompt
from pipecat_server.tools.workout_context import (
    TOOL_DEFINITIONS,
    TOOL_HANDLERS,
    create_session,
    end_session,
)


class PoseDataProcessor(FrameProcessor):
    """Process pose data from iOS client and inject into context."""

    # Key joint pairs for angle calculation
    # Note: iOS Vision framework uses names like "right_hip_joint", "right_knee_joint", etc.
    ANGLE_DEFINITIONS = {
        "right_knee": ("right_hip_joint", "right_knee_joint", "right_ankle_joint"),
        "left_knee": ("left_hip_joint", "left_knee_joint", "left_ankle_joint"),
        "right_hip": ("right_shoulder_joint", "right_hip_joint", "right_knee_joint"),
        "left_hip": ("left_shoulder_joint", "left_hip_joint", "left_knee_joint"),
        "right_elbow": ("right_shoulder_joint", "right_elbow_joint", "right_wrist_joint"),
        "left_elbow": ("left_shoulder_joint", "left_elbow_joint", "left_wrist_joint"),
        "right_shoulder": ("right_elbow_joint", "right_shoulder_joint", "right_hip_joint"),
        "left_shoulder": ("left_elbow_joint", "left_shoulder_joint", "left_hip_joint"),
    }

    def __init__(self, room_id: str):
        super().__init__()
        self.room_id = room_id
        self._last_pose_data = None
        self._last_pose_time = 0
        self._prev_angles = {}
        self._movement_direction = "neutral"  # up, down, hold

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process incoming frames, looking for pose data messages."""
        # Call super to handle StartFrame and other special frames
        await super().process_frame(frame, direction)
        # Then pass through all frames
        await self.push_frame(frame, direction)

    def update_pose_data(self, pose_data: dict):
        """Update the latest pose data from app message."""
        import time
        self._last_pose_data = pose_data
        self._last_pose_time = time.time()

        # Calculate angles and detect movement
        joints = pose_data.get("joints", {})
        angles = self._calculate_angles(joints)
        self._detect_movement(angles)
        self._prev_angles = angles

        logger.info(f"Pose received: {len(joints)} joints, angles: {angles}")

    def _calculate_angle(self, p1: dict, p2: dict, p3: dict) -> float:
        """Calculate angle at p2 formed by p1-p2-p3."""
        import math

        # Vector from p2 to p1
        v1 = (p1.get("x", 0) - p2.get("x", 0), p1.get("y", 0) - p2.get("y", 0))
        # Vector from p2 to p3
        v2 = (p3.get("x", 0) - p2.get("x", 0), p3.get("y", 0) - p2.get("y", 0))

        # Calculate angle using dot product
        dot = v1[0] * v2[0] + v1[1] * v2[1]
        mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
        mag2 = math.sqrt(v2[0]**2 + v2[1]**2)

        if mag1 * mag2 == 0:
            return 0

        cos_angle = max(-1, min(1, dot / (mag1 * mag2)))
        return math.degrees(math.acos(cos_angle))

    def _calculate_angles(self, joints: dict) -> dict:
        """Calculate all relevant joint angles."""
        angles = {}
        for angle_name, (j1, j2, j3) in self.ANGLE_DEFINITIONS.items():
            if j1 in joints and j2 in joints and j3 in joints:
                angles[angle_name] = round(self._calculate_angle(
                    joints[j1], joints[j2], joints[j3]
                ), 1)
        return angles

    def _detect_movement(self, current_angles: dict):
        """Detect movement direction based on angle changes."""
        if not self._prev_angles:
            return

        # Use primary angle (knee for squats/lunges, elbow for curls)
        for key in ["right_knee", "right_elbow", "right_hip"]:
            if key in current_angles and key in self._prev_angles:
                diff = current_angles[key] - self._prev_angles[key]
                if diff > 2:  # Angle increasing (extending)
                    self._movement_direction = "up"
                elif diff < -2:  # Angle decreasing (flexing)
                    self._movement_direction = "down"
                else:
                    self._movement_direction = "hold"
                break

    def get_pose_context_for_llm(self) -> str:
        """Get formatted pose context string for injection into LLM.

        Example output:
        [POSE DATA] Angles: right_knee=92°, right_hip=85°, right_elbow=165° | Movement: down | Phase: eccentric
        """
        if not self._last_pose_data:
            return ""

        joints = self._last_pose_data.get("joints", {})
        if not joints:
            return ""

        angles = self._calculate_angles(joints)
        if not angles:
            return ""

        # Format angles
        angle_strs = [f"{k}={v}°" for k, v in angles.items()]

        # Determine phase based on movement
        phase_map = {"down": "eccentric", "up": "concentric", "hold": "isometric"}
        phase = phase_map.get(self._movement_direction, "neutral")

        return f"[POSE] {', '.join(angle_strs)} | Movement: {self._movement_direction} | Phase: {phase}"

    @property
    def pose_context(self) -> str:
        """Get pose data as context string for LLM (legacy)."""
        return self.get_pose_context_for_llm()


class ToolExecutor(FrameProcessor):
    """Execute tool calls from Gemini and inject results."""

    def __init__(self, room_id: str):
        super().__init__()
        self.room_id = room_id

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames, handling tool calls."""
        # Must call parent to handle StartFrame properly
        await super().process_frame(frame, direction)


async def create_fitness_coach_bot(
    room_url: str,
    token: str,
    room_id: str,
    exercise_name: str,
    target_sets: int,
    target_reps: int,
    user_name: str = "there",
):
    """Create and run the fitness coach bot.

    Args:
        room_url: Daily room URL
        token: Daily room token
        room_id: Room identifier for session tracking
        exercise_name: Name of the exercise
        target_sets: Number of sets
        target_reps: Number of reps per set
        user_name: User's name for personalization
    """
    logger.info(f"Creating fitness coach bot for {exercise_name} ({target_sets}x{target_reps})")

    # Create workout session
    session = create_session(room_id, exercise_name, target_sets, target_reps)
    logger.info(f"Created workout session for room {room_id}")

    # Set up Daily transport (audio only - iOS handles video locally for pose detection)
    transport = DailyTransport(
        room_url=room_url,
        token=token,
        bot_name="Reppy Coach",
        params=DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            video_in_enabled=False,  # Disabled - iOS does local pose detection
            video_out_enabled=False,
            vad_enabled=True,
            vad_audio_passthrough=True,
            transcription_enabled=True,
        ),
    )

    # Create pose data processor
    pose_processor = PoseDataProcessor(room_id)

    # Get system prompt
    system_prompt = get_fitness_coach_prompt(
        exercise_name=exercise_name,
        target_sets=target_sets,
        target_reps=target_reps,
        user_name=user_name,
    )

    # Set up Gemini Live service (native audio I/O)
    llm = GeminiLiveLLMService(
        api_key=config.gemini.api_key,
        # Use default model (gemini-2.5-flash-native-audio-preview)
        voice_id="Puck",  # Energetic male voice for coaching
        system_instruction=system_prompt,
    )

    # Build initial context
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": f"I'm about to start {exercise_name}. Let me know when you can see me and we'll begin.",
        },
    ]

    # Create tool executor
    tool_executor = ToolExecutor(room_id)

    # Build pipeline: audio in -> Gemini Live (has native audio output) -> audio out
    pipeline = Pipeline([
        transport.input(),
        pose_processor,
        llm,
        transport.output(),
    ])

    # Handle app messages (pose data from iOS)
    @transport.event_handler("on_app_message")
    async def on_app_message(transport, message, sender):
        """Handle messages from iOS client."""
        logger.info(f"App message received from {sender}: {type(message)}")
        try:
            if isinstance(message, str):
                data = json.loads(message)
            elif isinstance(message, bytes):
                data = json.loads(message.decode('utf-8'))
            else:
                data = message

            msg_type = data.get("type")
            logger.info(f"App message type: {msg_type}")

            if msg_type == "pose_update":
                pose_processor.update_pose_data(data.get("data", {}))
            elif msg_type == "rep_completed":
                # iOS detected a rep - notify Gemini
                logger.info("Rep completed (from iOS)")
                rep_msg = [{"role": "user", "content": "[REP COMPLETED] The user just finished a rep. Acknowledge it!"}]
                await task.queue_frame(LLMMessagesAppendFrame(messages=rep_msg))
            elif msg_type == "set_completed":
                # iOS detected set completion - notify Gemini
                set_num = data.get("set_number", 0)
                reps = data.get("reps", 0)
                logger.info(f"Set {set_num} completed with {reps} reps (from iOS)")
                set_msg = [{"role": "user", "content": f"[SET COMPLETED] Set {set_num} done with {reps} reps. Encourage the user to rest!"}]
                await task.queue_frame(LLMMessagesAppendFrame(messages=set_msg))
            elif msg_type == "setup_issue":
                # iOS detected a setup issue - have AI coach guide the user
                issue_type = data.get("issue_type", "unknown")
                issue_message = data.get("message", "")
                logger.info(f"Setup issue: {issue_type} - {issue_message}")

                # Map issue types to coaching messages
                coaching_prompts = {
                    "not_in_frame": "[SETUP HELP] I can't see you! Please step into the camera frame so I can see your whole body.",
                    "legs_not_visible": "[SETUP HELP] I can only see your upper body. Please step back from the phone so I can see your legs too.",
                    "upper_body_not_visible": "[SETUP HELP] I can only see your lower body. Please adjust the phone angle or step forward slightly.",
                    "too_close": "[SETUP HELP] You're too close to the camera. Please step back about 6-8 feet so I can see your full body.",
                    "low_lighting": "[SETUP HELP] The lighting seems dim. If possible, move to a brighter area for better tracking.",
                    "phone_unstable": "[SETUP HELP] The camera seems to be moving. Please prop your phone against something stable.",
                }

                prompt = coaching_prompts.get(issue_type, f"[SETUP HELP] {issue_message}")
                setup_msg = [{"role": "user", "content": prompt}]
                await task.queue_frame(LLMMessagesAppendFrame(messages=setup_msg))
            else:
                logger.info(f"Unknown app message type: {msg_type}, data: {data}")

        except Exception as e:
            logger.error(f"Error processing app message: {e}")

    # Handle participant events
    @transport.event_handler("on_participant_joined")
    async def on_participant_joined(transport, participant):
        """Handle participant joining."""
        participant_id = participant.get("id", "unknown")
        is_local = participant.get("info", {}).get("isLocal", False)
        logger.info(f"Participant joined: {participant_id} (local={is_local})")

        # NOTE: We do NOT capture video from participants
        # iOS does local pose detection and sends pose data via app messages
        # This saves bandwidth and avoids camera conflicts on iOS

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        """Handle participant leaving."""
        participant_id = participant.get("id", "unknown")
        logger.info(f"Participant left: {participant_id}, reason: {reason}")
        # Clean up session
        end_session(room_id)

    # Create and run the pipeline task
    runner = PipelineRunner()
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
        ),
    )

    # Pose injection settings
    POSE_INJECTION_INTERVAL = 0.25  # 4 Hz (every 250ms)
    pose_injection_running = True

    async def inject_pose_data():
        """Background task to inject pose data into Gemini at 4 Hz."""
        last_context = ""
        injection_count = 0
        while pose_injection_running:
            try:
                await asyncio.sleep(POSE_INJECTION_INTERVAL)

                # Get current pose context
                pose_context = pose_processor.get_pose_context_for_llm()

                # Only send if we have data and it changed
                if pose_context and pose_context != last_context:
                    # Send as a system message to Gemini
                    # Using LLMMessagesAppendFrame to inject context
                    messages = [{"role": "user", "content": pose_context}]
                    await task.queue_frame(LLMMessagesAppendFrame(messages=messages))
                    injection_count += 1
                    if injection_count % 10 == 1:  # Log every 10th injection
                        logger.info(f"Pose injected ({injection_count}): {pose_context}")
                    last_context = pose_context

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Pose injection error: {e}")

    # Start pose injection task
    pose_task = asyncio.create_task(inject_pose_data())

    try:
        await runner.run(task)
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        pose_injection_running = False
        pose_task.cancel()
        try:
            await pose_task
        except asyncio.CancelledError:
            pass
        end_session(room_id)
        logger.info(f"Bot ended for room {room_id}")


async def run_bot(
    room_url: str,
    token: str,
    room_id: str,
    exercise_name: str,
    target_sets: int,
    target_reps: int,
    user_name: str = "there",
):
    """Entry point for running the bot in a separate process/task."""
    await create_fitness_coach_bot(
        room_url=room_url,
        token=token,
        room_id=room_id,
        exercise_name=exercise_name,
        target_sets=target_sets,
        target_reps=target_reps,
        user_name=user_name,
    )
