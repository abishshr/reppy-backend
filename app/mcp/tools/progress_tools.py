"""Progress tracking tools for MCP."""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    MealLog,
    UserProfile,
    WeightLog,
    WorkoutLog,
)
from app.mcp.tools.base import BaseTool, ToolResult


class LogWeightTool(BaseTool):
    """
    Log user's weight for tracking progress over time.

    This tool is called when the user wants to log their current weight.
    It creates a weight entry and updates their profile.
    """

    name = "log_weight"
    description = """Log the user's weight for progress tracking. Use this when the user
    mentions their weight or asks to track their weight. Example: 'I weigh 75kg today' or
    'Log my weight as 165 pounds'."""

    parameters = {
        "weight_kg": {
            "type": "number",
            "description": "Weight in kilograms. Convert from pounds if needed (divide by 2.205)",
        },
        "notes": {
            "type": "string",
            "description": "Optional notes about the weigh-in (e.g., 'morning weight', 'after workout')",
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Log the user's weight."""
        weight_kg = kwargs.get("weight_kg")
        notes = kwargs.get("notes")

        if not weight_kg or weight_kg <= 0:
            return ToolResult(
                success=False,
                error="Invalid weight value",
            )

        # Create weight log
        weight_log = WeightLog(
            user_id=self.user_id,
            weight_kg=weight_kg,
            logged_at=datetime.now(timezone.utc),
            notes=notes,
            source="chat",
        )
        self.db.add(weight_log)

        # Update profile's current weight
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == self.user_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            profile.weight_kg = weight_kg

        await self.db.commit()

        return ToolResult(
            success=True,
            data={
                "weight_kg": weight_kg,
                "notes": notes,
                "message": f"Weight logged: {weight_kg:.1f} kg",
            },
        )


class GetProgressSummaryTool(BaseTool):
    """
    Get a summary of the user's fitness progress.

    This tool retrieves progress data including weight trends, workout stats,
    and nutrition adherence to help provide progress updates.
    """

    name = "get_progress_summary"
    description = """Get the user's fitness progress summary including weight trends,
    workout statistics, and nutrition adherence. Use this when the user asks about
    their progress, how they're doing, or wants a fitness update."""

    parameters = {
        "days": {
            "type": "integer",
            "description": "Number of days to analyze (default: 30)",
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Get progress summary."""
        days = kwargs.get("days", 30)
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Get weight data
        weight_result = await self.db.execute(
            select(WeightLog)
            .where(WeightLog.user_id == self.user_id)
            .where(WeightLog.logged_at >= since)
            .order_by(WeightLog.logged_at)
        )
        weight_logs = list(weight_result.scalars().all())

        weight_data = None
        if weight_logs:
            weights = [log.weight_kg for log in weight_logs]
            weight_data = {
                "current": weights[-1],
                "starting": weights[0],
                "change": round(weights[-1] - weights[0], 2),
                "lowest": min(weights),
                "highest": max(weights),
                "entries": len(weight_logs),
            }

        # Get workout data
        workout_result = await self.db.execute(
            select(WorkoutLog)
            .where(WorkoutLog.user_id == self.user_id)
            .where(WorkoutLog.logged_at >= since)
        )
        workouts = list(workout_result.scalars().all())

        workout_data = {
            "total_workouts": len(workouts),
            "total_duration_min": sum(w.duration_min or 0 for w in workouts),
            "calories_burned": sum(w.calories_burned_est or 0 for w in workouts),
        }

        # Get nutrition data
        meal_result = await self.db.execute(
            select(MealLog)
            .where(MealLog.user_id == self.user_id)
            .where(MealLog.logged_at >= since)
        )
        meals = list(meal_result.scalars().all())

        # Calculate daily averages
        daily_totals: dict[str, dict] = {}
        for meal in meals:
            date_key = meal.logged_at.date().isoformat()
            if date_key not in daily_totals:
                daily_totals[date_key] = {"calories": 0, "protein": 0}
            daily_totals[date_key]["calories"] += meal.calories or 0
            daily_totals[date_key]["protein"] += meal.protein_g or 0

        num_days = len(daily_totals) if daily_totals else 1
        nutrition_data = {
            "total_meals": len(meals),
            "avg_daily_calories": round(sum(d["calories"] for d in daily_totals.values()) / num_days),
            "avg_daily_protein": round(sum(d["protein"] for d in daily_totals.values()) / num_days),
        }

        return ToolResult(
            success=True,
            data={
                "period_days": days,
                "weight": weight_data,
                "workouts": workout_data,
                "nutrition": nutrition_data,
            },
        )
