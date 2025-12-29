"""Streak tracking endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import get_db
from app.services.streak import StreakService, get_streak_service, StreakMilestone

router = APIRouter()


class StreakResponse(BaseModel):
    """Response for streak information."""
    current_streak: int
    longest_streak: int
    last_activity_date: str | None
    is_active_today: bool
    streak_at_risk: bool
    hours_until_break: int | None
    next_milestone: str | None
    days_to_next_milestone: int | None
    achieved_milestones: list[str]


class StreakUpdateResponse(BaseModel):
    """Response after updating streak."""
    streak: StreakResponse
    new_milestone: str | None
    milestone_message: str | None


MILESTONE_MESSAGES = {
    StreakMilestone.FIRST_DAY: "You've started your journey! Keep it going!",
    StreakMilestone.WEEK: "One week strong! You're building a great habit!",
    StreakMilestone.TWO_WEEKS: "Two weeks of consistency! You're on fire!",
    StreakMilestone.MONTH: "A full month! You're unstoppable!",
    StreakMilestone.TWO_MONTHS: "60 days of dedication! Incredible!",
    StreakMilestone.QUARTER: "90 days! You've made fitness a lifestyle!",
    StreakMilestone.HALF_YEAR: "Half a year! You're a true champion!",
    StreakMilestone.YEAR: "365 days! Legendary achievement!",
}


def get_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreakService:
    """Dependency to get streak service."""
    return get_streak_service(db)


@router.get("/", response_model=StreakResponse)
async def get_streak(
    current_user: CurrentUser,
    streak_service: Annotated[StreakService, Depends(get_service)],
) -> StreakResponse:
    """
    Get current streak information.

    Returns:
    - current_streak: Current consecutive days
    - longest_streak: All-time best streak
    - is_active_today: Whether user logged activity today
    - streak_at_risk: True if less than 12 hours until streak breaks
    - hours_until_break: Hours remaining before streak resets
    - next_milestone: Next milestone to achieve
    - days_to_next_milestone: Days needed to reach next milestone
    - achieved_milestones: List of achieved milestones
    """
    info = await streak_service.get_streak_info(current_user.id)
    return StreakResponse(**info.to_dict())


@router.post("/record", response_model=StreakUpdateResponse)
async def record_activity(
    current_user: CurrentUser,
    streak_service: Annotated[StreakService, Depends(get_service)],
) -> StreakUpdateResponse:
    """
    Manually record activity and update streak.

    This is called automatically when logging meals/workouts/water,
    but can also be called manually if needed.

    Returns the updated streak info and any newly achieved milestone.
    """
    info, new_milestone = await streak_service.record_activity(current_user.id)

    milestone_message = None
    if new_milestone:
        milestone_message = MILESTONE_MESSAGES.get(new_milestone)

    return StreakUpdateResponse(
        streak=StreakResponse(**info.to_dict()),
        new_milestone=new_milestone.value if new_milestone else None,
        milestone_message=milestone_message,
    )
