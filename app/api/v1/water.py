"""Water tracking API endpoints."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import get_current_user_id
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.models import WaterLog, UserProfile
from app.services.streak import get_streak_service

router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================


class WaterLogCreate(BaseModel):
    """Request to log water intake."""
    amount_ml: int = Field(..., gt=0, le=5000, description="Amount in milliliters (1-5000)")
    logged_at: Optional[datetime] = None
    source: str = "manual"


class WaterLogResponse(BaseModel):
    """Water log entry response."""
    id: str
    amount_ml: int
    logged_at: datetime
    source: str

    class Config:
        from_attributes = True


class WaterSummaryResponse(BaseModel):
    """Daily water intake summary."""
    date: str
    total_ml: int
    goal_ml: int
    percentage: float
    logs_count: int
    logs: list[WaterLogResponse]


class WaterStatsResponse(BaseModel):
    """Water intake statistics."""
    today_ml: int
    today_goal_ml: int
    today_percentage: float
    week_avg_ml: float
    week_goal_met_days: int
    streak_days: int


# ============================================================================
# Endpoints
# ============================================================================


@router.post("", response_model=WaterLogResponse, status_code=status.HTTP_201_CREATED)
async def log_water(
    data: WaterLogCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Log water intake."""
    log = WaterLog(
        user_id=user_id,
        amount_ml=data.amount_ml,
        logged_at=data.logged_at or datetime.utcnow(),
        source=data.source,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    # Update streak
    streak_service = get_streak_service(db)
    await streak_service.record_activity(user_id)

    return log


@router.get("/today", response_model=WaterSummaryResponse)
async def get_today_water(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get today's water intake summary."""
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())

    # Get user's water goal
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()
    goal_ml = profile.daily_water_goal_ml if profile and profile.daily_water_goal_ml else 2500

    # Get today's logs
    result = await db.execute(
        select(WaterLog)
        .where(
            and_(
                WaterLog.user_id == user_id,
                WaterLog.logged_at >= start_of_day,
                WaterLog.logged_at <= end_of_day,
            )
        )
        .order_by(WaterLog.logged_at.desc())
    )
    logs = result.scalars().all()

    total_ml = sum(log.amount_ml for log in logs)
    percentage = min((total_ml / goal_ml) * 100, 100) if goal_ml > 0 else 0

    return WaterSummaryResponse(
        date=today.isoformat(),
        total_ml=total_ml,
        goal_ml=goal_ml,
        percentage=round(percentage, 1),
        logs_count=len(logs),
        logs=[WaterLogResponse.model_validate(log) for log in logs],
    )


@router.get("/stats", response_model=WaterStatsResponse)
async def get_water_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get water intake statistics."""
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)

    # Get user's water goal
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()
    goal_ml = profile.daily_water_goal_ml if profile and profile.daily_water_goal_ml else 2500

    # Get today's total
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    today_result = await db.execute(
        select(func.coalesce(func.sum(WaterLog.amount_ml), 0))
        .where(
            and_(
                WaterLog.user_id == user_id,
                WaterLog.logged_at >= today_start,
                WaterLog.logged_at <= today_end,
            )
        )
    )
    today_ml = today_result.scalar() or 0

    # Get last 7 days data for averages and streak
    week_start = datetime.combine(week_ago, datetime.min.time())
    week_logs = await db.execute(
        select(
            func.date(WaterLog.logged_at).label("log_date"),
            func.sum(WaterLog.amount_ml).label("daily_total"),
        )
        .where(
            and_(
                WaterLog.user_id == user_id,
                WaterLog.logged_at >= week_start,
            )
        )
        .group_by(func.date(WaterLog.logged_at))
    )
    daily_totals = {row.log_date: row.daily_total for row in week_logs.all()}

    # Calculate week average
    week_total = sum(daily_totals.values())
    week_avg_ml = week_total / 7 if daily_totals else 0

    # Count days goal was met
    week_goal_met = sum(1 for total in daily_totals.values() if total >= goal_ml)

    # Calculate streak (consecutive days meeting goal, ending today)
    streak = 0
    check_date = today
    while True:
        if check_date in daily_totals and daily_totals[check_date] >= goal_ml:
            streak += 1
            check_date -= timedelta(days=1)
        elif check_date == today and today_ml >= goal_ml:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return WaterStatsResponse(
        today_ml=today_ml,
        today_goal_ml=goal_ml,
        today_percentage=min((today_ml / goal_ml) * 100, 100) if goal_ml > 0 else 0,
        week_avg_ml=round(week_avg_ml, 0),
        week_goal_met_days=week_goal_met,
        streak_days=streak,
    )


@router.get("/history", response_model=list[WaterSummaryResponse])
async def get_water_history(
    days: int = 7,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get water intake history for the past N days."""
    today = datetime.utcnow().date()

    # Get user's water goal
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()
    goal_ml = profile.daily_water_goal_ml if profile and profile.daily_water_goal_ml else 2500

    # Get logs for the period
    start_date = datetime.combine(today - timedelta(days=days - 1), datetime.min.time())
    result = await db.execute(
        select(WaterLog)
        .where(
            and_(
                WaterLog.user_id == user_id,
                WaterLog.logged_at >= start_date,
            )
        )
        .order_by(WaterLog.logged_at.desc())
    )
    all_logs = result.scalars().all()

    # Group by date
    logs_by_date: dict[str, list[WaterLog]] = {}
    for log in all_logs:
        date_str = log.logged_at.date().isoformat()
        if date_str not in logs_by_date:
            logs_by_date[date_str] = []
        logs_by_date[date_str].append(log)

    # Build response for each day
    history = []
    for i in range(days):
        check_date = today - timedelta(days=i)
        date_str = check_date.isoformat()
        day_logs = logs_by_date.get(date_str, [])
        total_ml = sum(log.amount_ml for log in day_logs)
        percentage = min((total_ml / goal_ml) * 100, 100) if goal_ml > 0 else 0

        history.append(
            WaterSummaryResponse(
                date=date_str,
                total_ml=total_ml,
                goal_ml=goal_ml,
                percentage=round(percentage, 1),
                logs_count=len(day_logs),
                logs=[WaterLogResponse.model_validate(log) for log in day_logs],
            )
        )

    return history


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_water_log(
    log_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a water log entry."""
    result = await db.execute(
        select(WaterLog).where(
            and_(WaterLog.id == log_id, WaterLog.user_id == user_id)
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Water log not found")

    await db.delete(log)
    await db.commit()


@router.patch("/goal")
async def update_water_goal(
    goal_ml: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update daily water goal."""
    if goal_ml < 500 or goal_ml > 10000:
        raise HTTPException(
            status_code=400,
            detail="Water goal must be between 500ml and 10000ml"
        )

    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.daily_water_goal_ml = goal_ml
    await db.commit()

    return {"goal_ml": goal_ml, "message": "Water goal updated"}
