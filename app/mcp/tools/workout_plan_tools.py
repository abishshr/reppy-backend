"""Workout planning tools for AI-generated workout programs."""

from datetime import datetime, timedelta, timezone
from typing import Any
import json as json_module

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import WorkoutPlan, WorkoutPlanDay, UserProfile
from app.mcp.tools.base import BaseTool, ToolResult


class GenerateWorkoutPlanTool(BaseTool):
    """Generate a personalized workout plan based on user's profile and goals."""

    name = "generate_workout_plan"
    description = """Generate and save a multi-week workout program. You MUST provide the complete workout data in the 'plan' parameter.

CRITICAL: The 'plan' parameter is REQUIRED and must contain a JSON array string with all workout days.

Example plan format (you must generate similar but complete data):
[{"week":1,"day":1,"day_name":"Push Day","workout_type":"strength","is_rest_day":false,"exercises":[{"name":"Bench Press","sets":4,"reps":"8-10","weight_suggestion":"moderate","rest_sec":90,"notes":"Control the descent"},{"name":"Shoulder Press","sets":3,"reps":"10-12","weight_suggestion":"light to moderate","rest_sec":60,"notes":"Keep core tight"}],"target_muscles":["chest","shoulders","triceps"],"estimated_duration_min":45,"notes":"Focus on mind-muscle connection"}]

Generate 16+ workout days for a 4-week program (4 days/week). Include varied exercises appropriate for the user's equipment and goals."""

    parameters = {
        "weeks": {
            "type": "integer",
            "description": "Number of weeks (1-12). Default: 4",
            "optional": True,
        },
        "days_per_week": {
            "type": "integer",
            "description": "Training days per week (1-6). Default: 4",
            "optional": True,
        },
        "goal": {
            "type": "string",
            "description": "Goal: strength, hypertrophy, endurance, fat_loss, general_fitness",
            "optional": True,
        },
        "difficulty": {
            "type": "string",
            "description": "Level: beginner, intermediate, advanced",
            "optional": True,
        },
        "split_type": {
            "type": "string",
            "description": "Split: full_body, upper_lower, push_pull_legs",
            "optional": True,
        },
        "plan": {
            "type": "string",
            "description": "REQUIRED: JSON array string of workout days. Each day: {week, day, day_name, workout_type, is_rest_day, exercises:[{name, sets, reps, weight_suggestion, rest_sec, notes}], target_muscles, estimated_duration_min, notes}",
        },
    }

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Store the generated workout plan."""
        print(f"[GenerateWorkoutPlanTool] kwargs: {kwargs}")

        plan_raw = kwargs.get("plan", "[]")
        weeks = kwargs.get("weeks", 4)
        days_per_week = kwargs.get("days_per_week", 4)
        goal = kwargs.get("goal", "general_fitness")
        difficulty = kwargs.get("difficulty", "intermediate")
        split_type = kwargs.get("split_type", "upper_lower")
        equipment_raw = kwargs.get("equipment", "gym")
        equipment = [e.strip() for e in equipment_raw.split(",")] if isinstance(equipment_raw, str) else equipment_raw

        print(f"[GenerateWorkoutPlanTool] plan_raw type: {type(plan_raw)}, length: {len(str(plan_raw))}")
        print(f"[GenerateWorkoutPlanTool] plan_raw preview: {str(plan_raw)[:500]}")
        print(f"[GenerateWorkoutPlanTool] plan_raw ending: ...{str(plan_raw)[-200:]}")

        # Parse plan data - could be a string or already a list
        if isinstance(plan_raw, str):
            # Replace Python None with JSON null (common AI output issue)
            plan_raw = plan_raw.replace(":None", ":null").replace(": None", ": null")
            try:
                plan_data = json_module.loads(plan_raw)
            except json_module.JSONDecodeError as e:
                print(f"[GenerateWorkoutPlanTool] JSON decode error: {e}")
                return ToolResult(
                    success=False,
                    error=f"Invalid JSON in plan data: {str(e)}",
                )
        else:
            plan_data = plan_raw

        # Handle if plan_data is a dict with "days" or "workouts" key
        if isinstance(plan_data, dict):
            if "days" in plan_data:
                plan_data = plan_data["days"]
            elif "workouts" in plan_data:
                plan_data = plan_data["workouts"]

        print(f"[GenerateWorkoutPlanTool] plan_data type: {type(plan_data)}, length: {len(plan_data) if isinstance(plan_data, list) else 'N/A'}")

        if not plan_data:
            return ToolResult(
                success=False,
                error="No workout plan data provided",
            )

        # Get user profile for context
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == self.user_id)
        )
        profile = result.scalar_one_or_none()

        # Create workout plan
        plan_name = f"{goal.replace('_', ' ').title()} - {split_type.replace('_', ' ').title()} ({weeks} weeks)"

        workout_plan = WorkoutPlan(
            user_id=self.user_id,
            name=plan_name,
            description=f"A {weeks}-week {difficulty} {goal.replace('_', ' ')} program using {split_type.replace('_', ' ')} split.",
            duration_weeks=weeks,
            days_per_week=days_per_week,
            goal=goal,
            difficulty=difficulty,
            equipment=equipment if isinstance(equipment, list) else [equipment],
            split_type=split_type,
            preferences={
                "user_goals": profile.goals if profile else [],
                "user_equipment": profile.equipment if profile else [],
            },
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(workout_plan)
        await self.db.flush()

        # Create plan days
        workout_days_created = 0
        for day_data in plan_data:
            # Handle if day_data is a string
            if isinstance(day_data, str):
                try:
                    day_data = json_module.loads(day_data)
                except json_module.JSONDecodeError:
                    continue

            if not isinstance(day_data, dict):
                continue

            week_number = day_data.get("week", 1)
            day_number = day_data.get("day", 1)
            exercises = day_data.get("exercises", [])
            is_rest_day = day_data.get("is_rest_day", False)

            plan_day = WorkoutPlanDay(
                workout_plan_id=workout_plan.id,
                week_number=week_number,
                day_number=day_number,
                day_name=day_data.get("day_name", f"Day {day_number}"),
                workout_type=day_data.get("workout_type", "strength"),
                exercises=exercises,
                target_muscles=day_data.get("target_muscles", []),
                estimated_duration_min=day_data.get("estimated_duration_min"),
                estimated_calories=day_data.get("estimated_calories"),
                notes=day_data.get("notes"),
                is_rest_day=is_rest_day,
            )
            self.db.add(plan_day)
            workout_days_created += 1

        await self.db.commit()

        return ToolResult(
            success=True,
            data={
                "workout_plan_id": workout_plan.id,
                "name": workout_plan.name,
                "duration_weeks": weeks,
                "days_per_week": days_per_week,
                "total_workout_days": workout_days_created,
                "goal": goal,
                "split_type": split_type,
            },
        )


class GetTodaysWorkoutTool(BaseTool):
    """Get today's workout from the active plan."""

    name = "get_todays_workout"
    description = """Get the next scheduled workout from the user's active workout plan.
    Use this when the user asks "what's my workout today?" or "what should I train today?"."""

    parameters = {}

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Get today's workout."""
        from sqlalchemy.orm import selectinload

        # Get active workout plan
        result = await self.db.execute(
            select(WorkoutPlan)
            .where(WorkoutPlan.user_id == self.user_id)
            .where(WorkoutPlan.is_active == True)
            .options(selectinload(WorkoutPlan.days))
            .order_by(WorkoutPlan.created_at.desc())
            .limit(1)
        )
        plan = result.scalar_one_or_none()

        if not plan:
            return ToolResult(
                success=False,
                error="No active workout plan found. Would you like me to create one?",
            )

        # Find the next incomplete workout
        incomplete_days = [
            day for day in plan.days
            if not day.is_completed and not day.is_rest_day
        ]

        if not incomplete_days:
            return ToolResult(
                success=True,
                data={
                    "message": "Congratulations! You've completed all workouts in this plan.",
                    "plan_name": plan.name,
                    "completed": True,
                },
            )

        # Sort by week then day and get the next one
        incomplete_days.sort(key=lambda d: (d.week_number, d.day_number))
        next_workout = incomplete_days[0]

        return ToolResult(
            success=True,
            data={
                "plan_name": plan.name,
                "week": next_workout.week_number,
                "day": next_workout.day_number,
                "day_name": next_workout.day_name,
                "workout_type": next_workout.workout_type,
                "exercises": next_workout.exercises,
                "target_muscles": next_workout.target_muscles,
                "estimated_duration_min": next_workout.estimated_duration_min,
                "notes": next_workout.notes,
                "workout_day_id": next_workout.id,
            },
        )


class CompleteWorkoutDayTool(BaseTool):
    """Mark a workout day as completed."""

    name = "complete_workout_day"
    description = """Mark a specific workout day as completed in the user's plan.
    Use this after the user finishes their scheduled workout."""

    parameters = {
        "workout_day_id": {
            "type": "string",
            "description": "ID of the workout day to mark as complete",
            "optional": True,
        },
    }

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Mark workout as completed."""
        workout_day_id = kwargs.get("workout_day_id")

        if workout_day_id:
            # Mark specific day
            result = await self.db.execute(
                select(WorkoutPlanDay)
                .join(WorkoutPlan)
                .where(WorkoutPlanDay.id == workout_day_id)
                .where(WorkoutPlan.user_id == self.user_id)
            )
            day = result.scalar_one_or_none()
        else:
            # Find the current/next workout to mark complete
            from sqlalchemy.orm import selectinload

            result = await self.db.execute(
                select(WorkoutPlan)
                .where(WorkoutPlan.user_id == self.user_id)
                .where(WorkoutPlan.is_active == True)
                .options(selectinload(WorkoutPlan.days))
                .limit(1)
            )
            plan = result.scalar_one_or_none()

            if not plan:
                return ToolResult(
                    success=False,
                    error="No active workout plan found.",
                )

            # Find next incomplete day
            incomplete = [d for d in plan.days if not d.is_completed and not d.is_rest_day]
            if not incomplete:
                return ToolResult(
                    success=False,
                    error="All workouts already completed.",
                )

            incomplete.sort(key=lambda d: (d.week_number, d.day_number))
            day = incomplete[0]

        if not day:
            return ToolResult(
                success=False,
                error="Workout day not found.",
            )

        day.is_completed = True
        day.completed_at = datetime.now(timezone.utc)
        await self.db.commit()

        return ToolResult(
            success=True,
            data={
                "message": f"Great job completing {day.day_name}!",
                "day_name": day.day_name,
                "week": day.week_number,
                "day": day.day_number,
            },
        )


class SuggestExerciseAlternativeTool(BaseTool):
    """Suggest an alternative exercise for one in the plan."""

    name = "suggest_exercise_alternative"
    description = """Suggest an alternative exercise when the user can't do a specific exercise.
    Use this when user says "I can't do X" or "what can I do instead of X?"."""

    parameters = {
        "original_exercise": {
            "type": "string",
            "description": "The exercise to find an alternative for",
        },
        "reason": {
            "type": "string",
            "description": "Why they can't do it: equipment, injury, preference",
            "optional": True,
        },
        "alternative_name": {
            "type": "string",
            "description": "Name of the suggested alternative exercise",
        },
        "alternative_description": {
            "type": "string",
            "description": "Brief description of how to perform it",
        },
        "target_muscles": {
            "type": "string",
            "description": "Comma-separated muscles targeted by the alternative (e.g., chest,shoulders,triceps)",
        },
        "why_good_alternative": {
            "type": "string",
            "description": "Why this is a good substitute",
        },
    }

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Return the exercise alternative suggestion."""
        target_muscles_raw = kwargs.get("target_muscles", "")
        target_muscles = [m.strip() for m in target_muscles_raw.split(",")] if target_muscles_raw else []

        return ToolResult(
            success=True,
            data={
                "original_exercise": kwargs.get("original_exercise"),
                "reason": kwargs.get("reason"),
                "alternative": {
                    "name": kwargs.get("alternative_name"),
                    "description": kwargs.get("alternative_description"),
                    "target_muscles": target_muscles,
                },
                "why_good_alternative": kwargs.get("why_good_alternative"),
            },
        )
