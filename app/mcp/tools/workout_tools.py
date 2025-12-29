"""Workout logging tools for MCP."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.infrastructure.database import WorkoutLog
from app.infrastructure.redis import redis_client
from app.mcp.tools.base import BaseTool, ToolResult


class LogWorkoutSuggestionTool(BaseTool):
    """
    Parse user's workout description and suggest a structured log.

    This tool is called when the user describes a workout.
    It returns a suggestion that requires confirmation before being logged.
    """

    name = "log_workout_suggestion"
    description = """Parse the user's workout description and return a structured
    suggestion. The suggestion requires user confirmation before being saved."""

    parameters = {
        "exercises": {
            "type": "array",
            "description": "List of exercises performed",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Exercise name"},
                    "sets": {"type": "integer", "description": "Number of sets"},
                    "reps": {"type": "integer", "description": "Reps per set"},
                    "weight_kg": {"type": "number", "description": "Weight in kg"},
                    "duration_min": {"type": "number", "description": "Duration in minutes"},
                    "rest_sec": {"type": "integer", "description": "Rest between sets in seconds"},
                },
            },
        },
        "workout_type": {
            "type": "string",
            "description": "Type of workout (strength, cardio, flexibility, mixed)",
        },
        "estimated_duration_min": {
            "type": "integer",
            "description": "Estimated total duration in minutes",
            "optional": True,
        },
        "estimated_calories_burned": {
            "type": "integer",
            "description": "Estimated calories burned",
            "optional": True,
        },
        "confidence": {
            "type": "number",
            "description": "Confidence score 0.0-1.0",
        },
        "notes": {
            "type": "string",
            "description": "Notes or tips about the workout",
            "optional": True,
        },
        "clarifying_questions": {
            "type": "array",
            "description": "Questions to ask if information is missing",
            "items": {"type": "string"},
            "optional": True,
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Create a workout suggestion and store it pending confirmation."""
        suggestion_id = str(uuid4())
        exercises = kwargs.get("exercises", [])
        workout_type = kwargs.get("workout_type")

        # Estimate duration if not provided
        duration_min = kwargs.get("estimated_duration_min")
        if not duration_min and exercises:
            # Estimate ~3 min per set for strength, or use exercise duration
            total_sets = sum(ex.get("sets", 1) for ex in exercises)
            total_exercise_duration = sum(ex.get("duration_min", 0) for ex in exercises)
            if total_exercise_duration > 0:
                duration_min = int(total_exercise_duration)
            else:
                duration_min = max(10, total_sets * 3)  # ~3 min per set, min 10 min

        # Estimate calories if not provided
        calories_burned = kwargs.get("estimated_calories_burned")
        if not calories_burned and duration_min:
            # Rough estimate: 5-8 cal/min depending on workout type
            cal_per_min = 8 if workout_type == "cardio" else 6 if workout_type == "strength" else 5
            calories_burned = duration_min * cal_per_min

        suggestion_data = {
            "user_id": self.user_id,
            "suggestion_id": suggestion_id,
            "exercises": exercises,
            "workout_type": workout_type,
            "duration_min": duration_min,
            "calories_burned_est": calories_burned,
            "confidence": kwargs.get("confidence", 0.5),
            "notes": kwargs.get("notes"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Store in Redis with 1-hour expiration
        await redis_client.set(
            f"workout_suggestion:{suggestion_id}",
            suggestion_data,
            expire_seconds=3600,
        )

        return ToolResult(
            success=True,
            data={
                "suggestion_id": suggestion_id,
                **suggestion_data,
                "clarifying_questions": kwargs.get("clarifying_questions", []),
            },
            requires_confirmation=True,
            suggestion_id=suggestion_id,
        )


class ConfirmWorkoutLogTool(BaseTool):
    """Confirm and save a workout suggestion to the database."""

    name = "confirm_log_workout"
    description = """Confirm a pending workout suggestion and save it to the database.
    Only call this after the user has confirmed the workout suggestion."""

    parameters = {
        "suggestion_id": {
            "type": "string",
            "description": "The ID of the pending workout suggestion to confirm",
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Confirm and save the workout to the database."""
        suggestion_id = kwargs.get("suggestion_id")

        if not suggestion_id:
            return ToolResult(
                success=False,
                error="suggestion_id is required",
            )

        # Retrieve the suggestion from Redis
        suggestion = await redis_client.get(f"workout_suggestion:{suggestion_id}")

        if not suggestion:
            return ToolResult(
                success=False,
                error="Suggestion not found or expired. Please create a new workout log.",
            )

        # Verify user owns this suggestion
        if suggestion.get("user_id") != self.user_id:
            return ToolResult(
                success=False,
                error="Unauthorized to confirm this suggestion",
            )

        # Create the workout log
        workout = WorkoutLog(
            user_id=self.user_id,
            logged_at=datetime.now(timezone.utc),
            workout_type=suggestion.get("workout_type"),
            exercises=suggestion.get("exercises", []),
            duration_min=suggestion.get("duration_min"),
            calories_burned_est=suggestion.get("calories_burned_est"),
            confidence=suggestion.get("confidence"),
            notes=suggestion.get("notes"),
        )

        self.db.add(workout)
        await self.db.flush()

        # Delete the suggestion from Redis
        await redis_client.delete(f"workout_suggestion:{suggestion_id}")

        return ToolResult(
            success=True,
            data={
                "workout_id": workout.id,
                "message": "Workout logged successfully",
                "exercises_count": len(workout.exercises),
                "duration_min": workout.duration_min,
            },
        )
