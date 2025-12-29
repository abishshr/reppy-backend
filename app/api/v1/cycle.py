"""Menstrual cycle tracking API endpoints."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import get_current_user_id
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.models import (
    MenstrualCycleLog,
    MenstrualCycleSettings,
    UserProfile,
)
from app.schemas.menstrual_cycle import (
    MenstrualLogCreate,
    MenstrualLogUpdate,
    MenstrualLogResponse,
    CycleSettingsUpdate,
    CycleSettingsResponse,
    CycleStatusResponse,
    CycleRecommendationsResponse,
    CalendarDayResponse,
    CycleHistoryResponse,
)
from app.services.cycle_analyzer import cycle_analyzer, CyclePhase

router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================


async def verify_female_user(user_id: str, db: AsyncSession) -> UserProfile:
    """Verify user is female and return profile."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if profile.sex != "female":
        raise HTTPException(
            status_code=403,
            detail="Cycle tracking is only available for female users"
        )

    return profile


async def get_or_create_settings(user_id: str, db: AsyncSession) -> MenstrualCycleSettings:
    """Get or create cycle settings for a user."""
    result = await db.execute(
        select(MenstrualCycleSettings).where(
            MenstrualCycleSettings.user_id == user_id
        )
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = MenstrualCycleSettings(
            id=str(uuid4()),
            user_id=user_id,
            average_cycle_length=28,
            average_period_length=5,
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return settings


# ============================================================================
# Cycle Log Endpoints
# ============================================================================


@router.post("/log", response_model=MenstrualLogResponse, status_code=status.HTTP_201_CREATED)
async def log_cycle_data(
    data: MenstrualLogCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Log menstrual cycle data for a specific date."""
    await verify_female_user(user_id, db)

    # Normalize date to start of day
    log_date = data.date.replace(hour=0, minute=0, second=0, microsecond=0)

    # Check if log already exists for this date
    existing = await db.execute(
        select(MenstrualCycleLog).where(
            and_(
                MenstrualCycleLog.user_id == user_id,
                func.date(MenstrualCycleLog.date) == log_date.date(),
            )
        )
    )
    existing_log = existing.scalar_one_or_none()

    if existing_log:
        # Update existing log
        if data.is_period_day is not None:
            existing_log.is_period_day = data.is_period_day
        if data.flow_intensity is not None:
            existing_log.flow_intensity = data.flow_intensity.value if hasattr(data.flow_intensity, 'value') else data.flow_intensity
        if data.symptoms is not None:
            existing_log.symptoms = data.symptoms
        if data.mood is not None:
            existing_log.mood = data.mood
        if data.energy_level is not None:
            existing_log.energy_level = data.energy_level
        if data.notes is not None:
            existing_log.notes = data.notes

        await db.commit()
        await db.refresh(existing_log)
        log = existing_log
    else:
        # Create new log
        log = MenstrualCycleLog(
            id=str(uuid4()),
            user_id=user_id,
            date=log_date,
            is_period_day=data.is_period_day,
            flow_intensity=data.flow_intensity.value if data.flow_intensity and hasattr(data.flow_intensity, 'value') else data.flow_intensity,
            symptoms=data.symptoms,
            mood=data.mood,
            energy_level=data.energy_level,
            notes=data.notes,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

    # Update last_period_start if this is a period day
    if data.is_period_day:
        settings = await get_or_create_settings(user_id, db)

        # Check if this is the start of a new period
        # (no period logged yesterday or this is earlier than current last_period_start)
        yesterday = log_date - timedelta(days=1)
        yesterday_result = await db.execute(
            select(MenstrualCycleLog).where(
                and_(
                    MenstrualCycleLog.user_id == user_id,
                    func.date(MenstrualCycleLog.date) == yesterday.date(),
                    MenstrualCycleLog.is_period_day == True,
                )
            )
        )
        yesterday_log = yesterday_result.scalar_one_or_none()

        if not yesterday_log:
            # This is the start of a new period
            if not settings.last_period_start or log_date > settings.last_period_start:
                # Calculate new average cycle length if we have previous data
                if settings.last_period_start:
                    days_between = (log_date - settings.last_period_start).days
                    if 21 <= days_between <= 45:
                        # Weighted average: 70% old, 30% new
                        new_avg = int(settings.average_cycle_length * 0.7 + days_between * 0.3)
                        settings.average_cycle_length = max(21, min(45, new_avg))

                settings.last_period_start = log_date
                await db.commit()

    return MenstrualLogResponse.model_validate(log)


@router.get("/today", response_model=MenstrualLogResponse | None)
async def get_today_log(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get today's menstrual log if exists."""
    await verify_female_user(user_id, db)

    today = datetime.utcnow().date()

    result = await db.execute(
        select(MenstrualCycleLog).where(
            and_(
                MenstrualCycleLog.user_id == user_id,
                func.date(MenstrualCycleLog.date) == today,
            )
        )
    )
    log = result.scalar_one_or_none()

    if not log:
        return None

    return MenstrualLogResponse.model_validate(log)


@router.patch("/log/{log_id}", response_model=MenstrualLogResponse)
async def update_log(
    log_id: str,
    data: MenstrualLogUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing cycle log."""
    await verify_female_user(user_id, db)

    result = await db.execute(
        select(MenstrualCycleLog).where(
            and_(
                MenstrualCycleLog.id == log_id,
                MenstrualCycleLog.user_id == user_id,
            )
        )
    )
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    if data.is_period_day is not None:
        log.is_period_day = data.is_period_day
    if data.flow_intensity is not None:
        log.flow_intensity = data.flow_intensity.value if hasattr(data.flow_intensity, 'value') else data.flow_intensity
    if data.symptoms is not None:
        log.symptoms = data.symptoms
    if data.mood is not None:
        log.mood = data.mood
    if data.energy_level is not None:
        log.energy_level = data.energy_level
    if data.notes is not None:
        log.notes = data.notes

    await db.commit()
    await db.refresh(log)

    return MenstrualLogResponse.model_validate(log)


@router.delete("/log/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_log(
    log_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a cycle log."""
    await verify_female_user(user_id, db)

    result = await db.execute(
        select(MenstrualCycleLog).where(
            and_(
                MenstrualCycleLog.id == log_id,
                MenstrualCycleLog.user_id == user_id,
            )
        )
    )
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    await db.delete(log)
    await db.commit()


# ============================================================================
# Cycle Status & Recommendations
# ============================================================================


@router.get("/status", response_model=CycleStatusResponse)
async def get_cycle_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get current cycle phase, day, and predictions."""
    await verify_female_user(user_id, db)
    settings = await get_or_create_settings(user_id, db)

    return cycle_analyzer.get_cycle_status(
        last_period_start=settings.last_period_start,
        avg_cycle_length=settings.average_cycle_length,
        avg_period_length=settings.average_period_length,
    )


@router.get("/recommendations", response_model=CycleRecommendationsResponse)
async def get_recommendations(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get nutrition and workout recommendations for current phase."""
    await verify_female_user(user_id, db)
    settings = await get_or_create_settings(user_id, db)

    status = cycle_analyzer.get_cycle_status(
        last_period_start=settings.last_period_start,
        avg_cycle_length=settings.average_cycle_length,
        avg_period_length=settings.average_period_length,
    )

    return cycle_analyzer.get_recommendations(status.current_phase)


# ============================================================================
# History & Calendar
# ============================================================================


@router.get("/history", response_model=CycleHistoryResponse)
async def get_history(
    days: int = Query(90, ge=7, le=365),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get cycle history for the last N days."""
    await verify_female_user(user_id, db)
    settings = await get_or_create_settings(user_id, db)

    start_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(MenstrualCycleLog)
        .where(
            and_(
                MenstrualCycleLog.user_id == user_id,
                MenstrualCycleLog.date >= start_date,
            )
        )
        .order_by(MenstrualCycleLog.date.desc())
    )
    logs = result.scalars().all()

    # Count total periods logged
    period_logs = [log for log in logs if log.is_period_day]

    return CycleHistoryResponse(
        logs=[MenstrualLogResponse.model_validate(log) for log in logs],
        average_cycle_length=settings.average_cycle_length,
        average_period_length=settings.average_period_length,
        last_period_start=settings.last_period_start,
        total_periods_logged=len(period_logs),
    )


@router.get("/calendar", response_model=list[CalendarDayResponse])
async def get_calendar(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get calendar view with period days, predictions, and phases."""
    await verify_female_user(user_id, db)
    settings = await get_or_create_settings(user_id, db)

    # Calculate date range for the month
    from calendar import monthrange
    _, days_in_month = monthrange(year, month)
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, days_in_month, 23, 59, 59)

    # Get logs for this month
    result = await db.execute(
        select(MenstrualCycleLog)
        .where(
            and_(
                MenstrualCycleLog.user_id == user_id,
                MenstrualCycleLog.date >= start_date,
                MenstrualCycleLog.date <= end_date,
            )
        )
    )
    logs = result.scalars().all()
    logs_by_date = {log.date.date(): log for log in logs}

    calendar_days = []
    ovulation_day = cycle_analyzer.get_ovulation_day(settings.average_cycle_length)

    for day in range(1, days_in_month + 1):
        current_date = datetime(year, month, day)
        log = logs_by_date.get(current_date.date())

        # Determine if this is a predicted period day
        is_predicted = False
        is_ovulation = False
        is_fertile = False
        phase = None

        if settings.last_period_start:
            cycle_day = cycle_analyzer.get_cycle_day(settings.last_period_start, current_date)

            # Adjust for cycles that have passed
            while cycle_day > settings.average_cycle_length:
                cycle_day -= settings.average_cycle_length

            phase_enum, _, _ = cycle_analyzer.get_current_phase(
                cycle_day,
                settings.average_cycle_length,
                settings.average_period_length
            )
            phase = phase_enum.value

            # Predicted period
            if cycle_day <= settings.average_period_length:
                is_predicted = True

            # Ovulation day
            if cycle_day == ovulation_day:
                is_ovulation = True

            # Fertile window
            is_fertile = cycle_analyzer.is_fertile_window(cycle_day, settings.average_cycle_length)

        calendar_days.append(CalendarDayResponse(
            date=current_date,
            is_period_day=log.is_period_day if log else False,
            is_predicted_period=is_predicted and not (log and log.is_period_day),
            is_fertile_window=is_fertile,
            is_ovulation_day=is_ovulation,
            phase=phase,
            has_log=log is not None,
            flow_intensity=log.flow_intensity if log else None,
            symptoms=log.symptoms if log else None,
            mood=log.mood if log else None,
            energy_level=log.energy_level if log else None,
        ))

    return calendar_days


# ============================================================================
# Settings
# ============================================================================


@router.get("/settings", response_model=CycleSettingsResponse)
async def get_settings(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get cycle settings."""
    await verify_female_user(user_id, db)
    settings = await get_or_create_settings(user_id, db)
    return CycleSettingsResponse.model_validate(settings)


@router.patch("/settings", response_model=CycleSettingsResponse)
async def update_settings(
    data: CycleSettingsUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update cycle settings."""
    await verify_female_user(user_id, db)
    settings = await get_or_create_settings(user_id, db)

    if data.average_cycle_length is not None:
        settings.average_cycle_length = data.average_cycle_length
    if data.average_period_length is not None:
        settings.average_period_length = data.average_period_length
    if data.last_period_start is not None:
        settings.last_period_start = data.last_period_start
    if data.notify_period_reminder is not None:
        settings.notify_period_reminder = data.notify_period_reminder
    if data.reminder_days_before is not None:
        settings.reminder_days_before = data.reminder_days_before

    await db.commit()
    await db.refresh(settings)

    return CycleSettingsResponse.model_validate(settings)
