"""Activity tracking endpoints (steps, etc.)."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import DailyActivity, UserProfile, get_db
from app.schemas import ActivityResponse, ActivitySummary, StepsSyncRequest

router = APIRouter()


@router.post("/steps/sync", response_model=ActivityResponse)
async def sync_steps(
    current_user: CurrentUser,
    steps_data: StepsSyncRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActivityResponse:
    """
    Sync daily steps from Apple Health.

    Uses upsert to handle multiple syncs for the same day.
    """
    # Convert date to datetime for storage
    activity_date = datetime.combine(
        steps_data.date,
        datetime.min.time(),
        tzinfo=timezone.utc,
    )

    # Upsert: insert or update if exists
    stmt = insert(DailyActivity).values(
        user_id=current_user.id,
        date=activity_date,
        steps=steps_data.steps,
        source=steps_data.source,
        synced_at=datetime.now(timezone.utc),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_user_date_source",
        set_={
            "steps": steps_data.steps,
            "synced_at": datetime.now(timezone.utc),
        },
    )
    await db.execute(stmt)
    await db.commit()

    # Fetch the updated/inserted record
    result = await db.execute(
        select(DailyActivity)
        .where(DailyActivity.user_id == current_user.id)
        .where(DailyActivity.date == activity_date)
        .where(DailyActivity.source == steps_data.source)
    )
    activity = result.scalar_one()

    return ActivityResponse.model_validate(activity)


@router.get("/steps", response_model=list[ActivityResponse])
async def get_steps_history(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=7, ge=1, le=90),
) -> list[ActivityResponse]:
    """Get step history for the past N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(DailyActivity)
        .where(DailyActivity.user_id == current_user.id)
        .where(DailyActivity.date >= since)
        .order_by(DailyActivity.date.desc())
    )
    activities = result.scalars().all()

    return [ActivityResponse.model_validate(a) for a in activities]


@router.get("/summary", response_model=ActivitySummary)
async def get_activity_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActivitySummary:
    """Get activity summary including today, 7-day average, and streak."""
    # Get user's step goal
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    step_goal = profile.daily_steps_goal if profile else 10000

    # Get last 7 days of activity
    week_start = datetime.now(timezone.utc) - timedelta(days=7)
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    result = await db.execute(
        select(DailyActivity)
        .where(DailyActivity.user_id == current_user.id)
        .where(DailyActivity.date >= week_start)
        .order_by(DailyActivity.date.desc())
    )
    activities = result.scalars().all()

    # Today's steps
    today_activity = next(
        (a for a in activities if a.date.date() == today_start.date()),
        None,
    )
    today_steps = today_activity.steps if today_activity else 0

    # Calculate 7-day average and total
    seven_day_total = sum(a.steps or 0 for a in activities)
    seven_day_average = seven_day_total / 7 if activities else 0

    # Calculate streak (consecutive days meeting goal)
    streak = 0
    for activity in sorted(activities, key=lambda a: a.date, reverse=True):
        if (activity.steps or 0) >= step_goal:
            streak += 1
        else:
            break

    return ActivitySummary(
        today_steps=today_steps,
        today_goal=step_goal,
        today_progress_percent=min(100.0, (today_steps / step_goal) * 100) if step_goal else 0,
        seven_day_average=round(seven_day_average, 1),
        seven_day_total=seven_day_total,
        streak_days=streak,
        daily_data=[ActivityResponse.model_validate(a) for a in activities],
    )
