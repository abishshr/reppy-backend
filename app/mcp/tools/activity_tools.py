"""Activity tracking tools for MCP."""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.infrastructure.database import DailyActivity, UserProfile
from app.mcp.tools.base import BaseTool, ToolResult


class GetActivitySummaryTool(BaseTool):
    """Get user's activity summary including steps."""

    name = "get_activity_summary"
    description = """Get the user's activity summary including today's steps,
    7-day average, and progress towards their daily goal. Use this to provide
    personalized activity-related advice."""

    parameters = {}  # No parameters needed

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Get activity summary for the user."""
        # Get user's step goal
        profile_result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == self.user_id)
        )
        profile = profile_result.scalar_one_or_none()
        step_goal = profile.daily_steps_goal if profile else 10000

        # Get last 7 days of activity
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_start = today_start - timedelta(days=7)

        result = await self.db.execute(
            select(DailyActivity)
            .where(DailyActivity.user_id == self.user_id)
            .where(DailyActivity.date >= week_start)
        )
        activities = result.scalars().all()

        # Today's steps
        today_activity = next(
            (a for a in activities if a.date.date() == today_start.date()),
            None,
        )
        today_steps = today_activity.steps if today_activity else 0

        # Calculate averages
        seven_day_total = sum(a.steps or 0 for a in activities)
        seven_day_average = seven_day_total / 7 if activities else 0

        # Calculate streak
        streak = 0
        for activity in sorted(activities, key=lambda a: a.date, reverse=True):
            if (activity.steps or 0) >= step_goal:
                streak += 1
            else:
                break

        remaining_steps = max(0, step_goal - today_steps)
        progress_percent = min(100.0, (today_steps / step_goal) * 100) if step_goal else 0

        return ToolResult(
            success=True,
            data={
                "today_steps": today_steps,
                "today_goal": step_goal,
                "remaining_steps": remaining_steps,
                "progress_percent": round(progress_percent, 1),
                "seven_day_average": round(seven_day_average, 1),
                "seven_day_total": seven_day_total,
                "streak_days": streak,
                "on_track": today_steps >= step_goal,
            },
        )
