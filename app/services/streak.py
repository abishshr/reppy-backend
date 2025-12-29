"""Streak tracking service for user engagement."""

from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import UserProfile, MealLog, WorkoutLog, WaterLog


class StreakMilestone(str, Enum):
    """Streak milestone achievements."""
    FIRST_DAY = "first_day"  # 1 day
    WEEK = "week"  # 7 days
    TWO_WEEKS = "two_weeks"  # 14 days
    MONTH = "month"  # 30 days
    TWO_MONTHS = "two_months"  # 60 days
    QUARTER = "quarter"  # 90 days
    HALF_YEAR = "half_year"  # 180 days
    YEAR = "year"  # 365 days


MILESTONE_DAYS = {
    StreakMilestone.FIRST_DAY: 1,
    StreakMilestone.WEEK: 7,
    StreakMilestone.TWO_WEEKS: 14,
    StreakMilestone.MONTH: 30,
    StreakMilestone.TWO_MONTHS: 60,
    StreakMilestone.QUARTER: 90,
    StreakMilestone.HALF_YEAR: 180,
    StreakMilestone.YEAR: 365,
}


class StreakInfo:
    """Streak information for a user."""

    def __init__(
        self,
        current_streak: int,
        longest_streak: int,
        last_activity_date: Optional[datetime],
        is_active_today: bool,
        streak_at_risk: bool,
        hours_until_break: Optional[int],
        next_milestone: Optional[StreakMilestone],
        days_to_next_milestone: Optional[int],
        achieved_milestones: list[StreakMilestone],
    ):
        self.current_streak = current_streak
        self.longest_streak = longest_streak
        self.last_activity_date = last_activity_date
        self.is_active_today = is_active_today
        self.streak_at_risk = streak_at_risk
        self.hours_until_break = hours_until_break
        self.next_milestone = next_milestone
        self.days_to_next_milestone = days_to_next_milestone
        self.achieved_milestones = achieved_milestones

    def to_dict(self) -> dict:
        return {
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "last_activity_date": self.last_activity_date.isoformat() if self.last_activity_date else None,
            "is_active_today": self.is_active_today,
            "streak_at_risk": self.streak_at_risk,
            "hours_until_break": self.hours_until_break,
            "next_milestone": self.next_milestone.value if self.next_milestone else None,
            "days_to_next_milestone": self.days_to_next_milestone,
            "achieved_milestones": [m.value for m in self.achieved_milestones],
        }


class StreakService:
    """Service for managing user streaks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_streak_info(self, user_id: str) -> StreakInfo:
        """
        Get comprehensive streak information for a user.

        Args:
            user_id: User ID

        Returns:
            StreakInfo with current streak status
        """
        # Get user profile
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await self.db.execute(stmt)
        profile = result.scalar_one_or_none()

        if not profile:
            return StreakInfo(
                current_streak=0,
                longest_streak=0,
                last_activity_date=None,
                is_active_today=False,
                streak_at_risk=False,
                hours_until_break=None,
                next_milestone=StreakMilestone.FIRST_DAY,
                days_to_next_milestone=1,
                achieved_milestones=[],
            )

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Check if user has activity today
        is_active_today = await self._has_activity_today(user_id, today_start)

        # Calculate hours until streak breaks
        hours_until_break = None
        streak_at_risk = False

        if profile.last_activity_date:
            # Normalize to naive datetime for comparison
            last_activity = profile.last_activity_date.replace(tzinfo=None) if profile.last_activity_date.tzinfo else profile.last_activity_date
            grace_deadline = last_activity + timedelta(hours=profile.streak_grace_hours)
            time_remaining = grace_deadline - now

            if time_remaining.total_seconds() > 0:
                hours_until_break = int(time_remaining.total_seconds() / 3600)
                # Streak is at risk if less than 12 hours remaining
                streak_at_risk = hours_until_break < 12 and not is_active_today
            elif not is_active_today:
                # Streak has already broken but we'll update it on next activity
                hours_until_break = 0

        # Get milestones
        achieved = self._get_achieved_milestones(profile.current_streak)
        next_milestone, days_to_next = self._get_next_milestone(profile.current_streak)

        return StreakInfo(
            current_streak=profile.current_streak,
            longest_streak=profile.longest_streak,
            last_activity_date=profile.last_activity_date,
            is_active_today=is_active_today,
            streak_at_risk=streak_at_risk,
            hours_until_break=hours_until_break,
            next_milestone=next_milestone,
            days_to_next_milestone=days_to_next,
            achieved_milestones=achieved,
        )

    async def record_activity(self, user_id: str) -> tuple[StreakInfo, Optional[StreakMilestone]]:
        """
        Record user activity and update streak.

        Call this after logging a meal, workout, or water.

        Args:
            user_id: User ID

        Returns:
            Tuple of (updated StreakInfo, newly achieved milestone if any)
        """
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await self.db.execute(stmt)
        profile = result.scalar_one_or_none()

        if not profile:
            return await self.get_streak_info(user_id), None

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        old_streak = profile.current_streak
        new_milestone = None

        if profile.last_activity_date:
            last_activity_date = profile.last_activity_date.replace(tzinfo=None) if profile.last_activity_date.tzinfo else profile.last_activity_date
            last_activity_day = last_activity_date.replace(hour=0, minute=0, second=0, microsecond=0)
            grace_deadline = last_activity_date + timedelta(hours=profile.streak_grace_hours)

            # Check if this is a new day
            if today_start > last_activity_day:
                if now <= grace_deadline:
                    # Within grace period - extend streak
                    profile.current_streak += 1
                else:
                    # Grace period expired - reset streak
                    profile.current_streak = 1
            # Same day - streak stays the same, just update last_activity_date
        else:
            # First activity ever
            profile.current_streak = 1

        # Update longest streak if needed
        if profile.current_streak > profile.longest_streak:
            profile.longest_streak = profile.current_streak

        # Update last activity date
        profile.last_activity_date = now

        # Check if new milestone achieved
        if profile.current_streak > old_streak:
            for milestone, days in MILESTONE_DAYS.items():
                if old_streak < days <= profile.current_streak:
                    new_milestone = milestone
                    break

        await self.db.commit()
        await self.db.refresh(profile)

        streak_info = await self.get_streak_info(user_id)
        return streak_info, new_milestone

    async def _has_activity_today(self, user_id: str, today_start: datetime) -> bool:
        """Check if user has logged any activity today."""
        tomorrow_start = today_start + timedelta(days=1)

        # Check meals
        meal_stmt = select(MealLog).where(
            MealLog.user_id == user_id,
            MealLog.logged_at >= today_start,
            MealLog.logged_at < tomorrow_start,
        ).limit(1)
        meal_result = await self.db.execute(meal_stmt)
        if meal_result.scalar_one_or_none():
            return True

        # Check workouts
        workout_stmt = select(WorkoutLog).where(
            WorkoutLog.user_id == user_id,
            WorkoutLog.logged_at >= today_start,
            WorkoutLog.logged_at < tomorrow_start,
        ).limit(1)
        workout_result = await self.db.execute(workout_stmt)
        if workout_result.scalar_one_or_none():
            return True

        # Check water logs
        water_stmt = select(WaterLog).where(
            WaterLog.user_id == user_id,
            WaterLog.logged_at >= today_start,
            WaterLog.logged_at < tomorrow_start,
        ).limit(1)
        water_result = await self.db.execute(water_stmt)
        if water_result.scalar_one_or_none():
            return True

        return False

    def _get_achieved_milestones(self, current_streak: int) -> list[StreakMilestone]:
        """Get list of milestones the user has achieved."""
        achieved = []
        for milestone, days in MILESTONE_DAYS.items():
            if current_streak >= days:
                achieved.append(milestone)
        return achieved

    def _get_next_milestone(self, current_streak: int) -> tuple[Optional[StreakMilestone], Optional[int]]:
        """Get the next milestone and days remaining."""
        for milestone, days in MILESTONE_DAYS.items():
            if current_streak < days:
                return milestone, days - current_streak
        return None, None  # All milestones achieved!


def get_streak_service(db: AsyncSession) -> StreakService:
    """Get a StreakService instance."""
    return StreakService(db)
