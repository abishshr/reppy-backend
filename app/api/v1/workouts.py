"""Workout logging endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import WorkoutLog, get_db
from app.schemas import WorkoutLogCreate, WorkoutLogResponse, PRInfo
from app.schemas.workout import PersonalRecordResponse, ExerciseAttempt
from app.services.streak import get_streak_service
from app.services.personal_records import get_pr_service

router = APIRouter()


@router.get("/", response_model=list[WorkoutLogResponse])
async def list_workouts(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[WorkoutLogResponse]:
    """List recent workouts for the current user."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(WorkoutLog)
        .where(WorkoutLog.user_id == current_user.id)
        .where(WorkoutLog.logged_at >= since)
        .order_by(WorkoutLog.logged_at.desc())
        .limit(limit)
    )
    workouts = result.scalars().all()

    return [WorkoutLogResponse.model_validate(w) for w in workouts]


@router.post("/", response_model=WorkoutLogResponse, status_code=status.HTTP_201_CREATED)
async def create_workout(
    current_user: CurrentUser,
    workout_data: WorkoutLogCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkoutLogResponse:
    """Log a new workout."""
    logged_at = workout_data.logged_at or datetime.now(timezone.utc)

    workout = WorkoutLog(
        user_id=current_user.id,
        logged_at=logged_at,
        workout_type=workout_data.workout_type,
        exercises=[ex.model_dump() for ex in workout_data.exercises],
        duration_min=workout_data.duration_min,
        calories_burned_est=workout_data.calories_burned_est,
        confidence=workout_data.confidence,
        notes=workout_data.notes,
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)

    # Check for PRs on each exercise
    pr_service = get_pr_service(db)
    new_prs: list[PRInfo] = []

    for exercise in workout_data.exercises:
        if not exercise.name:
            continue

        pr_update = await pr_service.check_and_update_pr(
            user_id=current_user.id,
            exercise_name=exercise.name,
            weight_kg=exercise.weight_kg,
            reps=exercise.reps,
            sets=exercise.sets,
            workout_id=workout.id,
            logged_at=logged_at,
        )

        # Add any new PRs to the response
        if pr_update.is_new_weight_pr and pr_update.new_weight_kg:
            new_prs.append(PRInfo(
                exercise_name=pr_update.exercise_name,
                pr_type="weight",
                new_value=pr_update.new_weight_kg,
                previous_value=pr_update.previous_weight_kg,
                unit="kg",
            ))

        if pr_update.is_new_volume_pr and pr_update.new_volume_kg:
            new_prs.append(PRInfo(
                exercise_name=pr_update.exercise_name,
                pr_type="volume",
                new_value=pr_update.new_volume_kg,
                previous_value=pr_update.previous_volume_kg,
                unit="kg (volume)",
            ))

        if pr_update.is_new_reps_pr and pr_update.new_reps:
            new_prs.append(PRInfo(
                exercise_name=pr_update.exercise_name,
                pr_type="reps",
                new_value=float(pr_update.new_reps),
                previous_value=float(pr_update.previous_reps) if pr_update.previous_reps else None,
                unit="reps",
            ))

    # Update streak
    streak_service = get_streak_service(db)
    await streak_service.record_activity(current_user.id)

    # Build response with PRs
    response = WorkoutLogResponse.model_validate(workout)
    response.new_prs = new_prs

    return response


@router.get("/{workout_id}", response_model=WorkoutLogResponse)
async def get_workout(
    workout_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkoutLogResponse:
    """Get a specific workout by ID."""
    result = await db.execute(
        select(WorkoutLog)
        .where(WorkoutLog.id == workout_id)
        .where(WorkoutLog.user_id == current_user.id)
    )
    workout = result.scalar_one_or_none()

    if not workout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout not found",
        )

    return WorkoutLogResponse.model_validate(workout)


@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workout(
    workout_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a workout log."""
    result = await db.execute(
        select(WorkoutLog)
        .where(WorkoutLog.id == workout_id)
        .where(WorkoutLog.user_id == current_user.id)
    )
    workout = result.scalar_one_or_none()

    if not workout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout not found",
        )

    await db.delete(workout)
    await db.commit()


@router.get("/summary/week")
async def get_week_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get this week's workout summary."""
    week_start = datetime.now(timezone.utc) - timedelta(days=7)

    result = await db.execute(
        select(WorkoutLog)
        .where(WorkoutLog.user_id == current_user.id)
        .where(WorkoutLog.logged_at >= week_start)
    )
    workouts = result.scalars().all()

    # Count by type
    type_counts: dict[str, int] = {}
    for w in workouts:
        wtype = w.workout_type or "other"
        type_counts[wtype] = type_counts.get(wtype, 0) + 1

    return {
        "period_start": week_start.date().isoformat(),
        "period_end": datetime.now(timezone.utc).date().isoformat(),
        "workout_count": len(workouts),
        "total_duration_min": sum(w.duration_min or 0 for w in workouts),
        "total_calories_burned": sum(w.calories_burned_est or 0 for w in workouts),
        "by_type": type_counts,
    }


# =============================================================================
# Personal Records Endpoints
# =============================================================================


@router.get("/personal-records", response_model=list[PersonalRecordResponse])
async def get_personal_records(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PersonalRecordResponse]:
    """Get all personal records for the current user."""
    pr_service = get_pr_service(db)
    prs = await pr_service.get_user_prs(current_user.id, limit=limit)
    return [PersonalRecordResponse.model_validate(pr) for pr in prs]


@router.get("/personal-records/recent", response_model=list[PersonalRecordResponse])
async def get_recent_prs(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=7, ge=1, le=30),
) -> list[PersonalRecordResponse]:
    """Get PRs set within the last N days."""
    pr_service = get_pr_service(db)
    prs = await pr_service.get_recent_prs(current_user.id, days=days)
    return [PersonalRecordResponse.model_validate(pr) for pr in prs]


@router.get("/exercise/{exercise_name}/pr", response_model=PersonalRecordResponse)
async def get_exercise_pr(
    exercise_name: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PersonalRecordResponse:
    """Get personal record for a specific exercise."""
    pr_service = get_pr_service(db)
    pr = await pr_service.get_exercise_pr(current_user.id, exercise_name)

    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No records found for exercise: {exercise_name}",
        )

    return PersonalRecordResponse.model_validate(pr)


@router.get("/exercise/{exercise_name}/history", response_model=list[ExerciseAttempt])
async def get_exercise_history(
    exercise_name: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=50),
) -> list[ExerciseAttempt]:
    """Get history of attempts for a specific exercise."""
    pr_service = get_pr_service(db)
    history = await pr_service.get_exercise_history(
        current_user.id, exercise_name, limit=limit
    )
    return [ExerciseAttempt(**h) for h in history]


@router.get("/exercise/{exercise_name}/last", response_model=ExerciseAttempt)
async def get_last_exercise_attempt(
    exercise_name: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExerciseAttempt:
    """Get the most recent attempt of an exercise (for showing 'last time' in UI)."""
    pr_service = get_pr_service(db)
    last_attempt = await pr_service.get_last_attempt(current_user.id, exercise_name)

    if not last_attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No previous attempts found for exercise: {exercise_name}",
        )

    return ExerciseAttempt(**last_attempt)
