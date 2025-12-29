"""Workout context tools for Pipecat AI Coach."""

from typing import Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WorkoutSession:
    """Current workout session state."""
    exercise_name: str
    target_sets: int
    target_reps: int
    current_set: int = 1
    current_reps: int = 0
    completed_sets: list[dict] = field(default_factory=list)
    form_corrections: list[dict] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "exercise_name": self.exercise_name,
            "target_sets": self.target_sets,
            "target_reps": self.target_reps,
            "current_set": self.current_set,
            "current_reps": self.current_reps,
            "completed_sets": self.completed_sets,
            "form_corrections_count": len(self.form_corrections),
            "duration_seconds": (datetime.now() - self.started_at).total_seconds(),
        }


# In-memory session storage (per room)
_sessions: dict[str, WorkoutSession] = {}


def create_session(room_id: str, exercise_name: str, target_sets: int, target_reps: int) -> WorkoutSession:
    """Create a new workout session."""
    session = WorkoutSession(
        exercise_name=exercise_name,
        target_sets=target_sets,
        target_reps=target_reps,
    )
    _sessions[room_id] = session
    return session


def get_session(room_id: str) -> WorkoutSession | None:
    """Get the current workout session."""
    return _sessions.get(room_id)


def end_session(room_id: str) -> WorkoutSession | None:
    """End and remove a workout session."""
    return _sessions.pop(room_id, None)


# Tool definitions for Gemini
def get_workout_context_tool() -> dict:
    """Tool definition for getting workout context."""
    return {
        "name": "get_workout_context",
        "description": "Get the current workout context including exercise name, sets, reps, and progress. Call this when you need to know the current state of the workout.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }


def log_form_correction_tool() -> dict:
    """Tool definition for logging form corrections."""
    return {
        "name": "log_form_correction",
        "description": "Log a form correction that was given to the user. Use this to track corrections for later analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "correction_type": {
                    "type": "string",
                    "description": "Type of correction (e.g., 'depth', 'knee_tracking', 'back_position')"
                },
                "correction_text": {
                    "type": "string",
                    "description": "The correction message that was spoken"
                },
                "severity": {
                    "type": "string",
                    "enum": ["minor", "moderate", "critical"],
                    "description": "Severity of the form issue"
                }
            },
            "required": ["correction_type", "correction_text"]
        }
    }


def increment_rep_tool() -> dict:
    """Tool definition for incrementing rep count."""
    return {
        "name": "increment_rep",
        "description": "Increment the rep count when a full rep is completed. Call this each time you count a rep.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }


def complete_set_tool() -> dict:
    """Tool definition for completing a set."""
    return {
        "name": "complete_set",
        "description": "Mark the current set as complete and move to rest/next set. Call when target reps are reached or user indicates set is done.",
        "parameters": {
            "type": "object",
            "properties": {
                "actual_reps": {
                    "type": "integer",
                    "description": "The actual number of reps completed in this set"
                }
            },
            "required": ["actual_reps"]
        }
    }


# Tool implementations
async def get_workout_context(room_id: str, **kwargs) -> dict:
    """Get current workout context."""
    session = get_session(room_id)
    if not session:
        return {"error": "No active session"}
    return session.to_dict()


async def log_form_correction(
    room_id: str,
    correction_type: str,
    correction_text: str,
    severity: str = "minor"
) -> dict:
    """Log a form correction."""
    session = get_session(room_id)
    if not session:
        return {"error": "No active session"}

    correction = {
        "type": correction_type,
        "text": correction_text,
        "severity": severity,
        "timestamp": datetime.now().isoformat(),
        "set_number": session.current_set,
        "rep_number": session.current_reps,
    }
    session.form_corrections.append(correction)
    return {"status": "logged", "correction": correction}


async def increment_rep(room_id: str, **kwargs) -> dict:
    """Increment rep count."""
    session = get_session(room_id)
    if not session:
        return {"error": "No active session"}

    session.current_reps += 1
    return {
        "status": "incremented",
        "current_reps": session.current_reps,
        "target_reps": session.target_reps,
        "set_complete": session.current_reps >= session.target_reps,
    }


async def complete_set(room_id: str, actual_reps: int) -> dict:
    """Complete the current set."""
    session = get_session(room_id)
    if not session:
        return {"error": "No active session"}

    completed = {
        "set_number": session.current_set,
        "reps": actual_reps,
        "timestamp": datetime.now().isoformat(),
    }
    session.completed_sets.append(completed)
    session.current_set += 1
    session.current_reps = 0

    workout_complete = session.current_set > session.target_sets

    return {
        "status": "set_complete",
        "completed": completed,
        "next_set": session.current_set if not workout_complete else None,
        "workout_complete": workout_complete,
    }


# Map tool names to implementations
TOOL_HANDLERS = {
    "get_workout_context": get_workout_context,
    "log_form_correction": log_form_correction,
    "increment_rep": increment_rep,
    "complete_set": complete_set,
}

TOOL_DEFINITIONS = [
    get_workout_context_tool(),
    log_form_correction_tool(),
    increment_rep_tool(),
    complete_set_tool(),
]
