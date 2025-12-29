"""RAG context assembler for AI conversations."""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import (
    DailyActivity,
    MealLog,
    UserMemory,
    UserProfile,
    WorkoutLog,
)


class ContextAssembler:
    """Assembles relevant context for AI conversations using RAG pattern."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def assemble_context(self, user_id: str, intent: str = "") -> dict[str, Any]:
        """
        Assemble context for the AI model.

        This implements the RAG pattern - retrieving only relevant facts
        instead of feeding full history.
        """
        context: dict[str, Any] = {}

        # Get user profile
        context["profile"] = await self._get_profile(user_id)

        # Calculate daily targets and remaining macros
        context["targets"] = await self._get_targets(user_id)
        context["remaining_macros"] = await self._get_remaining_macros(user_id)

        # Get recent meals (last 7 days)
        context["recent_meals"] = await self._get_recent_meals(user_id, days=7)

        # Get recent workouts (last 7 days)
        context["recent_workouts"] = await self._get_recent_workouts(user_id, days=7)

        # Get activity summary (steps)
        context["activity"] = await self._get_activity_summary(user_id)

        # Get learned memories/preferences
        context["memories"] = await self._get_user_memories(user_id)

        return context

    async def _get_profile(self, user_id: str) -> dict[str, Any] | None:
        """Get user profile facts."""
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            return None

        return {
            "name": profile.name,
            "age": profile.age,
            "sex": profile.sex,
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
            "activity_level": profile.activity_level,
            "goals": profile.goals or [],
            "diet_style": profile.diet_style,
            "allergies": profile.allergies or [],
            "equipment": profile.equipment or [],
        }

    async def _get_targets(self, user_id: str) -> dict[str, Any]:
        """Get daily targets."""
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            return {}

        return {
            "daily_calories": profile.daily_calorie_target,
            "daily_protein_g": profile.daily_protein_target,
            "daily_carbs_g": profile.daily_carbs_target,
            "daily_fat_g": profile.daily_fat_target,
            "daily_steps": profile.daily_steps_goal,
        }

    async def _get_remaining_macros(self, user_id: str) -> dict[str, Any]:
        """Calculate remaining macros for today."""
        # Get today's meals
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        result = await self.db.execute(
            select(MealLog)
            .where(MealLog.user_id == user_id)
            .where(MealLog.logged_at >= today_start)
        )
        meals = result.scalars().all()

        # Sum consumed macros
        consumed = {
            "calories": sum(m.calories or 0 for m in meals),
            "protein_g": sum(m.protein_g or 0 for m in meals),
            "carbs_g": sum(m.carbs_g or 0 for m in meals),
            "fat_g": sum(m.fat_g or 0 for m in meals),
        }

        # Get targets
        targets = await self._get_targets(user_id)

        return {
            "consumed": consumed,
            "remaining": {
                "calories": (targets.get("daily_calories") or 0) - consumed["calories"],
                "protein_g": (targets.get("daily_protein_g") or 0) - consumed["protein_g"],
                "carbs_g": (targets.get("daily_carbs_g") or 0) - consumed["carbs_g"],
                "fat_g": (targets.get("daily_fat_g") or 0) - consumed["fat_g"],
            },
        }

    async def _get_recent_meals(self, user_id: str, days: int = 7) -> list[dict]:
        """Get recent meal summaries."""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(MealLog)
            .where(MealLog.user_id == user_id)
            .where(MealLog.logged_at >= since)
            .order_by(MealLog.logged_at.desc())
            .limit(20)
        )
        meals = result.scalars().all()

        return [
            {
                "logged_at": m.logged_at.isoformat(),
                "meal_type": m.meal_type,
                "items": m.items,
                "calories": m.calories,
                "protein_g": m.protein_g,
            }
            for m in meals
        ]

    async def _get_recent_workouts(self, user_id: str, days: int = 7) -> list[dict]:
        """Get recent workout summaries."""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(WorkoutLog)
            .where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.logged_at >= since)
            .order_by(WorkoutLog.logged_at.desc())
            .limit(10)
        )
        workouts = result.scalars().all()

        return [
            {
                "logged_at": w.logged_at.isoformat(),
                "workout_type": w.workout_type,
                "exercises": w.exercises,
                "duration_min": w.duration_min,
            }
            for w in workouts
        ]

    async def _get_activity_summary(self, user_id: str) -> dict[str, Any]:
        """Get activity (steps) summary."""
        # Get today and 7-day data
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_start = datetime.now(timezone.utc) - timedelta(days=7)

        result = await self.db.execute(
            select(DailyActivity)
            .where(DailyActivity.user_id == user_id)
            .where(DailyActivity.date >= week_start)
        )
        activities = result.scalars().all()

        today_activity = next(
            (a for a in activities if a.date.date() == today_start.date()),
            None,
        )

        seven_day_total = sum(a.steps or 0 for a in activities)

        return {
            "today_steps": today_activity.steps if today_activity else 0,
            "seven_day_average": round(seven_day_total / 7, 1) if activities else 0,
            "seven_day_total": seven_day_total,
        }

    async def _get_user_memories(self, user_id: str) -> dict[str, list[str]]:
        """Get learned user preferences organized by category."""
        result = await self.db.execute(
            select(UserMemory)
            .where(UserMemory.user_id == user_id)
            .where(UserMemory.is_active == True)
            .order_by(UserMemory.confidence.desc())
        )
        memories = result.scalars().all()

        # Organize by category
        categorized: dict[str, list[str]] = {
            "food_preferences": [],
            "food_dislikes": [],
            "workout_habits": [],
            "schedule": [],
            "health_notes": [],
            "goals": [],
            "other": [],
        }

        category_mapping = {
            "food_preference": "food_preferences",
            "food_dislike": "food_dislikes",
            "workout_habit": "workout_habits",
            "schedule": "schedule",
            "health_note": "health_notes",
            "goal": "goals",
            "other": "other",
        }

        for memory in memories:
            category_key = category_mapping.get(memory.category, "other")
            categorized[category_key].append(memory.fact)

        # Filter out empty categories
        return {k: v for k, v in categorized.items() if v}
