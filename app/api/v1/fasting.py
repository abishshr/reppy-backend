"""API endpoints for intermittent fasting tracking."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser, get_current_user_id
from app.infrastructure.database import get_db
from app.infrastructure.database.models import FastingSession, FastingSettings
from app.schemas.fasting import (
    PROTOCOL_DURATIONS,
    ActiveFastResponse,
    FastingHistoryResponse,
    FastingProtocol,
    FastingProtocolInfo,
    FastingSessionCreate,
    FastingSessionResponse,
    FastingSessionStop,
    FastingSettingsResponse,
    FastingSettingsUpdate,
    FastingStatsResponse,
    FastingStatus,
)
from app.services.streak import get_streak_service

router = APIRouter()


def compute_session_progress(session: FastingSession) -> FastingSessionResponse:
    """Compute elapsed/remaining time and progress for a fasting session."""
    now = datetime.now(timezone.utc)
    started = session.started_at.replace(tzinfo=timezone.utc) if session.started_at.tzinfo is None else session.started_at
    target_end = session.target_end_at.replace(tzinfo=timezone.utc) if session.target_end_at.tzinfo is None else session.target_end_at

    total_seconds = (target_end - started).total_seconds()
    elapsed_seconds = int((now - started).total_seconds())
    remaining_seconds = max(0, int((target_end - now).total_seconds()))

    if session.status == "completed" and session.actual_end_at:
        actual_end = session.actual_end_at.replace(tzinfo=timezone.utc) if session.actual_end_at.tzinfo is None else session.actual_end_at
        elapsed_seconds = int((actual_end - started).total_seconds())
        remaining_seconds = 0
        progress_percentage = 100.0
    elif session.status == "cancelled":
        progress_percentage = min(100.0, (elapsed_seconds / total_seconds) * 100) if total_seconds > 0 else 0
    else:
        progress_percentage = min(100.0, (elapsed_seconds / total_seconds) * 100) if total_seconds > 0 else 0

    return FastingSessionResponse(
        id=session.id,
        user_id=session.user_id,
        protocol=session.protocol,
        started_at=session.started_at,
        target_end_at=session.target_end_at,
        actual_end_at=session.actual_end_at,
        status=session.status,
        duration_hours=session.duration_hours,
        notes=session.notes,
        created_at=session.created_at,
        elapsed_seconds=elapsed_seconds,
        remaining_seconds=remaining_seconds,
        progress_percentage=round(progress_percentage, 1),
    )


@router.post("", response_model=FastingSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_fast(
    data: FastingSessionCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FastingSessionResponse:
    """Start a new fasting session.

    Ends any active fasting session before starting a new one.
    """
    # Check for active fast and end it
    active_result = await db.execute(
        select(FastingSession)
        .where(FastingSession.user_id == current_user.id)
        .where(FastingSession.status == "active")
    )
    active_fast = active_result.scalar_one_or_none()

    if active_fast:
        # Auto-cancel the previous active fast
        active_fast.status = "cancelled"
        active_fast.actual_end_at = datetime.now(timezone.utc)

    # Determine duration
    if data.protocol == FastingProtocol.CUSTOM:
        if data.duration_hours is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="duration_hours is required for custom protocol",
            )
        duration_hours = data.duration_hours
    else:
        duration_hours = PROTOCOL_DURATIONS.get(data.protocol, 16)

    now = datetime.now(timezone.utc)
    target_end = now + timedelta(hours=duration_hours)

    session = FastingSession(
        user_id=current_user.id,
        protocol=data.protocol.value,
        started_at=now,
        target_end_at=target_end,
        status="active",
        duration_hours=duration_hours,
        notes=data.notes,
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    return compute_session_progress(session)


@router.post("/stop", response_model=FastingSessionResponse)
async def stop_fast(
    data: FastingSessionStop,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FastingSessionResponse:
    """End the current fasting session."""
    result = await db.execute(
        select(FastingSession)
        .where(FastingSession.user_id == current_user.id)
        .where(FastingSession.status == "active")
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active fasting session found",
        )

    now = datetime.now(timezone.utc)
    session.actual_end_at = now
    session.status = "completed" if data.completed else "cancelled"

    if data.notes:
        session.notes = (session.notes or "") + f"\n{data.notes}".strip()

    # Update fasting streak if completed
    if data.completed:
        settings_result = await db.execute(
            select(FastingSettings).where(FastingSettings.user_id == current_user.id)
        )
        settings = settings_result.scalar_one_or_none()

        if settings:
            # Check if this continues the streak (within 48 hours of last fast)
            if settings.last_fast_completed_at:
                last_completed = settings.last_fast_completed_at.replace(tzinfo=timezone.utc) if settings.last_fast_completed_at.tzinfo is None else settings.last_fast_completed_at
                hours_since_last = (now - last_completed).total_seconds() / 3600
                if hours_since_last <= 48:
                    settings.current_fasting_streak += 1
                else:
                    settings.current_fasting_streak = 1
            else:
                settings.current_fasting_streak = 1

            settings.longest_fasting_streak = max(
                settings.longest_fasting_streak, settings.current_fasting_streak
            )
            settings.last_fast_completed_at = now

    await db.commit()
    await db.refresh(session)

    # Update general streak
    streak_service = get_streak_service(db)
    await streak_service.record_activity(current_user.id)

    return compute_session_progress(session)


@router.get("/active", response_model=ActiveFastResponse)
async def get_active_fast(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActiveFastResponse:
    """Get the user's active fasting session with real-time progress."""
    result = await db.execute(
        select(FastingSession)
        .where(FastingSession.user_id == current_user.id)
        .where(FastingSession.status == "active")
    )
    session = result.scalar_one_or_none()

    if not session:
        # Check eating window
        settings_result = await db.execute(
            select(FastingSettings).where(FastingSettings.user_id == current_user.id)
        )
        settings = settings_result.scalar_one_or_none()

        eating_window_active = False
        next_start = None
        next_end = None

        if settings and settings.eating_window_start and settings.eating_window_end:
            now = datetime.now(timezone.utc)
            today = now.date()

            start_time = datetime.strptime(settings.eating_window_start, "%H:%M").time()
            end_time = datetime.strptime(settings.eating_window_end, "%H:%M").time()

            window_start = datetime.combine(today, start_time, tzinfo=timezone.utc)
            window_end = datetime.combine(today, end_time, tzinfo=timezone.utc)

            if window_end < window_start:
                # Eating window crosses midnight
                if now.time() >= start_time or now.time() < end_time:
                    eating_window_active = True
            else:
                if start_time <= now.time() <= end_time:
                    eating_window_active = True

            if not eating_window_active:
                # Calculate next eating window
                if now.time() < start_time:
                    next_start = window_start
                    next_end = window_end
                else:
                    next_start = window_start + timedelta(days=1)
                    next_end = window_end + timedelta(days=1)

        return ActiveFastResponse(
            is_fasting=False,
            session=None,
            eating_window_active=eating_window_active,
            next_eating_window_starts=next_start,
            next_eating_window_ends=next_end,
        )

    return ActiveFastResponse(
        is_fasting=True,
        session=compute_session_progress(session),
        eating_window_active=False,
    )


@router.get("/history", response_model=FastingHistoryResponse)
async def get_fasting_history(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> FastingHistoryResponse:
    """Get paginated fasting history."""
    offset = (page - 1) * page_size

    # Get total count
    count_result = await db.execute(
        select(func.count(FastingSession.id)).where(
            FastingSession.user_id == current_user.id
        )
    )
    total = count_result.scalar() or 0

    # Get sessions
    result = await db.execute(
        select(FastingSession)
        .where(FastingSession.user_id == current_user.id)
        .order_by(FastingSession.started_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    sessions = result.scalars().all()

    return FastingHistoryResponse(
        items=[compute_session_progress(s) for s in sessions],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(sessions)) < total,
    )


@router.get("/stats", response_model=FastingStatsResponse)
async def get_fasting_stats(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FastingStatsResponse:
    """Get fasting statistics."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Get completed fasts
    result = await db.execute(
        select(FastingSession)
        .where(FastingSession.user_id == current_user.id)
        .where(FastingSession.status == "completed")
    )
    completed_fasts = result.scalars().all()

    # Calculate stats
    total_fasts = len(completed_fasts)
    total_hours = sum(
        (f.actual_end_at - f.started_at).total_seconds() / 3600
        for f in completed_fasts
        if f.actual_end_at
    )
    avg_duration = total_hours / total_fasts if total_fasts > 0 else 0

    # Count by protocol
    protocol_counts: dict[str, int] = {}
    for f in completed_fasts:
        protocol_counts[f.protocol] = protocol_counts.get(f.protocol, 0) + 1

    most_used = max(protocol_counts.items(), key=lambda x: x[1])[0] if protocol_counts else None

    # This week/month counts
    this_week = sum(1 for f in completed_fasts if f.started_at >= week_ago)
    this_month = sum(1 for f in completed_fasts if f.started_at >= month_ago)

    # Get streak from settings
    settings_result = await db.execute(
        select(FastingSettings).where(FastingSettings.user_id == current_user.id)
    )
    settings = settings_result.scalar_one_or_none()

    return FastingStatsResponse(
        current_fasting_streak=settings.current_fasting_streak if settings else 0,
        longest_fasting_streak=settings.longest_fasting_streak if settings else 0,
        total_fasts_completed=total_fasts,
        total_hours_fasted=round(total_hours, 1),
        average_fast_duration_hours=round(avg_duration, 1),
        most_used_protocol=most_used,
        this_week_fasts=this_week,
        this_month_fasts=this_month,
        fasts_by_protocol=protocol_counts,
    )


@router.get("/settings", response_model=FastingSettingsResponse)
async def get_fasting_settings(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FastingSettingsResponse:
    """Get user's fasting settings."""
    result = await db.execute(
        select(FastingSettings).where(FastingSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # Create default settings
        settings = FastingSettings(
            user_id=current_user.id,
            notify_fast_complete=True,
            notify_reminder_before_min=30,
            current_fasting_streak=0,
            longest_fasting_streak=0,
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return FastingSettingsResponse.model_validate(settings)


@router.patch("/settings", response_model=FastingSettingsResponse)
async def update_fasting_settings(
    data: FastingSettingsUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FastingSettingsResponse:
    """Update user's fasting settings."""
    result = await db.execute(
        select(FastingSettings).where(FastingSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = FastingSettings(user_id=current_user.id)
        db.add(settings)

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    await db.commit()
    await db.refresh(settings)

    return FastingSettingsResponse.model_validate(settings)


@router.get("/protocols", response_model=list[FastingProtocolInfo])
async def get_protocols() -> list[FastingProtocolInfo]:
    """Get all available fasting protocols with descriptions."""
    return [
        FastingProtocolInfo(
            protocol="16:8",
            name="16:8 Intermittent Fasting",
            description="Fast for 16 hours, eat within an 8-hour window. Most popular and sustainable protocol.",
            fasting_hours=16,
            eating_hours=8,
            difficulty="easy",
            recommended_for=["beginners", "weight_loss", "general_health"],
        ),
        FastingProtocolInfo(
            protocol="18:6",
            name="18:6 Intermittent Fasting",
            description="Fast for 18 hours, eat within a 6-hour window. More intense than 16:8.",
            fasting_hours=18,
            eating_hours=6,
            difficulty="moderate",
            recommended_for=["intermediate", "weight_loss", "metabolic_health"],
        ),
        FastingProtocolInfo(
            protocol="20:4",
            name="20:4 Warrior Diet",
            description="Fast for 20 hours, eat within a 4-hour window. Also known as the Warrior Diet.",
            fasting_hours=20,
            eating_hours=4,
            difficulty="advanced",
            recommended_for=["advanced", "autophagy", "fat_loss"],
        ),
        FastingProtocolInfo(
            protocol="omad",
            name="One Meal A Day (OMAD)",
            description="Eat one large meal per day within a 1-hour window. 23 hours of fasting.",
            fasting_hours=23,
            eating_hours=1,
            difficulty="advanced",
            recommended_for=["advanced", "simplicity", "autophagy"],
        ),
        FastingProtocolInfo(
            protocol="24h",
            name="24-Hour Fast",
            description="Full day fast from dinner to dinner or lunch to lunch.",
            fasting_hours=24,
            eating_hours=0,
            difficulty="advanced",
            recommended_for=["experienced", "reset", "autophagy"],
        ),
        FastingProtocolInfo(
            protocol="36h",
            name="36-Hour Fast",
            description="Extended fast lasting 36 hours. Significant autophagy benefits.",
            fasting_hours=36,
            eating_hours=0,
            difficulty="expert",
            recommended_for=["experienced", "deep_autophagy", "metabolic_reset"],
        ),
        FastingProtocolInfo(
            protocol="48h",
            name="48-Hour Fast",
            description="Two-day extended fast. Consult a doctor before attempting.",
            fasting_hours=48,
            eating_hours=0,
            difficulty="expert",
            recommended_for=["experienced", "therapeutic", "research"],
        ),
        FastingProtocolInfo(
            protocol="5:2",
            name="5:2 Diet",
            description="Eat normally 5 days, restrict calories (500-600) on 2 non-consecutive days.",
            fasting_hours=16,
            eating_hours=8,
            difficulty="moderate",
            recommended_for=["flexibility", "weight_management", "beginners"],
        ),
        FastingProtocolInfo(
            protocol="custom",
            name="Custom Fast",
            description="Set your own fasting duration.",
            fasting_hours=0,
            eating_hours=0,
            difficulty="varies",
            recommended_for=["advanced", "personalization"],
        ),
    ]


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fasting_session(
    session_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a fasting session from history."""
    result = await db.execute(
        select(FastingSession)
        .where(FastingSession.id == session_id)
        .where(FastingSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fasting session not found",
        )

    await db.delete(session)
    await db.commit()
