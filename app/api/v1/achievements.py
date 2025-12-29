"""Achievements endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import (
    Achievement,
    UserAchievement,
    WorkoutLog,
    WeightLog,
    get_db,
)
from app.schemas.progress import (
    AchievementProgress,
    AchievementResponse,
    UserAchievementResponse,
)

router = APIRouter()


@router.get("/", response_model=list[AchievementResponse])
async def list_achievements(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AchievementResponse]:
    """List all available achievements."""
    result = await db.execute(
        select(Achievement).order_by(Achievement.category, Achievement.points)
    )
    achievements = result.scalars().all()
    return [AchievementResponse.model_validate(a) for a in achievements]


@router.get("/my", response_model=list[UserAchievementResponse])
async def list_my_achievements(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserAchievementResponse]:
    """List achievements unlocked by the current user."""
    result = await db.execute(
        select(UserAchievement)
        .where(UserAchievement.user_id == current_user.id)
        .options(selectinload(UserAchievement.achievement))
        .order_by(UserAchievement.unlocked_at.desc())
    )
    user_achievements = result.scalars().all()
    return [UserAchievementResponse.model_validate(ua) for ua in user_achievements]


@router.get("/progress", response_model=list[AchievementProgress])
async def get_achievement_progress(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AchievementProgress]:
    """Get progress toward all achievements."""
    # Get all achievements
    achievements_result = await db.execute(select(Achievement))
    achievements = achievements_result.scalars().all()

    # Get user's unlocked achievements
    unlocked_result = await db.execute(
        select(UserAchievement).where(UserAchievement.user_id == current_user.id)
    )
    unlocked = {ua.achievement_id: ua for ua in unlocked_result.scalars().all()}

    # Calculate current values for different requirement types
    current_values = await _calculate_user_stats(current_user.id, db)

    progress_list = []
    for achievement in achievements:
        is_unlocked = achievement.id in unlocked
        current_value = current_values.get(achievement.requirement_type, 0)

        progress_list.append(
            AchievementProgress(
                achievement=AchievementResponse.model_validate(achievement),
                current_value=current_value,
                target_value=achievement.requirement_value,
                progress_percent=min(
                    100.0, (current_value / achievement.requirement_value) * 100
                )
                if achievement.requirement_value > 0
                else 0,
                is_unlocked=is_unlocked,
                unlocked_at=unlocked[achievement.id].unlocked_at if is_unlocked else None,
            )
        )

    return progress_list


@router.get("/points")
async def get_achievement_points(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get total achievement points for the user."""
    result = await db.execute(
        select(func.sum(Achievement.points))
        .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
        .where(UserAchievement.user_id == current_user.id)
    )
    total_points = result.scalar() or 0

    # Get count
    count_result = await db.execute(
        select(func.count(UserAchievement.id)).where(
            UserAchievement.user_id == current_user.id
        )
    )
    unlocked_count = count_result.scalar() or 0

    # Get total achievements
    total_result = await db.execute(select(func.count(Achievement.id)))
    total_achievements = total_result.scalar() or 0

    return {
        "total_points": total_points,
        "unlocked_count": unlocked_count,
        "total_achievements": total_achievements,
        "completion_percent": round(
            (unlocked_count / total_achievements) * 100, 1
        )
        if total_achievements > 0
        else 0,
    }


@router.get("/{achievement_id}", response_model=AchievementResponse)
async def get_achievement(
    achievement_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    """Get a specific achievement."""
    result = await db.execute(
        select(Achievement).where(Achievement.id == achievement_id)
    )
    achievement = result.scalar_one_or_none()

    if not achievement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achievement not found",
        )

    return AchievementResponse.model_validate(achievement)


async def _calculate_user_stats(user_id: str, db: AsyncSession) -> dict[str, int]:
    """Calculate user stats for achievement progress."""
    stats = {}

    # Total workouts
    workout_count = await db.execute(
        select(func.count(WorkoutLog.id)).where(WorkoutLog.user_id == user_id)
    )
    stats["workout_count"] = workout_count.scalar() or 0

    # Weight logs (for streak calculation, simplified)
    weight_count = await db.execute(
        select(func.count(WeightLog.id)).where(WeightLog.user_id == user_id)
    )
    stats["weight_log_count"] = weight_count.scalar() or 0

    # Add more stat calculations as needed
    # stats["streak_days"] = calculate_streak(...)
    # stats["total_volume_kg"] = calculate_volume(...)

    return stats
