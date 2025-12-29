"""Workout planning endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import WorkoutPlan, WorkoutPlanDay, get_db
from app.infrastructure.external.exercisedb import get_exercisedb_client
from app.infrastructure.external.musclewiki import get_musclewiki_client

router = APIRouter()


# MARK: - Schemas

class ExerciseResponse(BaseModel):
    name: str
    sets: int | None = None
    reps: str | None = None  # Can be "8-12" or "10"
    weight_kg: float | None = None
    weight_suggestion: str | None = None  # e.g., "moderate weight"
    rest_sec: int | None = None
    tempo: str | None = None  # e.g., "3-1-2-0"
    notes: str | None = None
    is_superset: bool = False
    superset_with: str | None = None
    # ExerciseDB enrichment
    gif_url: str | None = None
    target_muscle: str | None = None
    instructions: list[str] | None = None
    secondary_muscles: list[str] | None = None
    # MuscleWiki enrichment (video)
    video_url: str | None = None


class ExerciseSearchResult(BaseModel):
    """Search result for exercise database lookup."""
    name: str
    target_muscle: str | None = None
    secondary_muscles: list[str] | None = None
    equipment: str | None = None
    difficulty: str | None = None
    gif_url: str | None = None
    video_url: str | None = None
    instructions: list[str] | None = None


async def enrich_exercises_with_images(exercises: list[dict]) -> list[dict]:
    """Enrich exercises with GIF URLs and instructions from ExerciseDB."""
    client = get_exercisedb_client()
    enriched = []

    for exercise in exercises:
        name = exercise.get("name", "")
        # Only fetch if not already enriched
        if name and not exercise.get("gif_url"):
            try:
                db_exercise = await client.search_exercise(name)
                if db_exercise:
                    exercise["gif_url"] = db_exercise.get("gif_url")
                    exercise["target_muscle"] = db_exercise.get("target_muscle")
                    exercise["instructions"] = db_exercise.get("instructions", [])
                    exercise["secondary_muscles"] = db_exercise.get("secondary_muscles", [])
            except Exception as e:
                print(f"Failed to enrich exercise {name}: {e}")
        enriched.append(exercise)

    return enriched


class WorkoutPlanDayResponse(BaseModel):
    id: str
    week_number: int
    day_number: int
    day_name: str | None
    workout_type: str | None
    exercises: list[dict]
    target_muscles: list[str] | None
    estimated_duration_min: int | None
    estimated_calories: int | None
    notes: str | None
    is_rest_day: bool
    is_completed: bool
    completed_at: datetime | None

    class Config:
        from_attributes = True


class WorkoutPlanResponse(BaseModel):
    id: str
    name: str
    description: str | None
    duration_weeks: int
    days_per_week: int
    goal: str | None
    difficulty: str | None
    equipment: list[str] | None
    split_type: str | None
    is_active: bool
    current_week: int
    current_day: int
    started_at: datetime | None
    created_at: datetime
    days: list[WorkoutPlanDayResponse] = []

    class Config:
        from_attributes = True


class WorkoutPlanSummaryResponse(BaseModel):
    id: str
    name: str
    description: str | None
    duration_weeks: int
    days_per_week: int
    goal: str | None
    difficulty: str | None
    split_type: str | None
    is_active: bool
    current_week: int
    current_day: int
    total_workouts: int
    completed_workouts: int
    progress_percent: float

    class Config:
        from_attributes = True


class MarkDayCompleteRequest(BaseModel):
    workout_day_id: str


# MARK: - Workout Plan Endpoints

@router.get("", response_model=list[WorkoutPlanSummaryResponse])
async def get_workout_plans(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = True,
) -> list[WorkoutPlanSummaryResponse]:
    """Get all workout plans for the current user."""
    query = (
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == current_user.id)
        .options(selectinload(WorkoutPlan.days))
    )

    if active_only:
        query = query.where(WorkoutPlan.is_active == True)

    query = query.order_by(WorkoutPlan.created_at.desc())

    result = await db.execute(query)
    plans = result.scalars().all()

    summaries = []
    for plan in plans:
        workout_days = [d for d in plan.days if not d.is_rest_day]
        completed = len([d for d in workout_days if d.is_completed])
        total = len(workout_days)
        progress = (completed / total * 100) if total > 0 else 0

        summaries.append(
            WorkoutPlanSummaryResponse(
                id=plan.id,
                name=plan.name,
                description=plan.description,
                duration_weeks=plan.duration_weeks,
                days_per_week=plan.days_per_week,
                goal=plan.goal,
                difficulty=plan.difficulty,
                split_type=plan.split_type,
                is_active=plan.is_active,
                current_week=plan.current_week,
                current_day=plan.current_day,
                total_workouts=total,
                completed_workouts=completed,
                progress_percent=round(progress, 1),
            )
        )

    return summaries


@router.get("/active", response_model=WorkoutPlanResponse | None)
async def get_active_workout_plan(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkoutPlanResponse | None:
    """Get the currently active workout plan with all days."""
    result = await db.execute(
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == current_user.id)
        .where(WorkoutPlan.is_active == True)
        .options(selectinload(WorkoutPlan.days))
        .order_by(WorkoutPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        return None

    return WorkoutPlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        duration_weeks=plan.duration_weeks,
        days_per_week=plan.days_per_week,
        goal=plan.goal,
        difficulty=plan.difficulty,
        equipment=plan.equipment,
        split_type=plan.split_type,
        is_active=plan.is_active,
        current_week=plan.current_week,
        current_day=plan.current_day,
        started_at=plan.started_at,
        created_at=plan.created_at,
        days=[
            WorkoutPlanDayResponse(
                id=day.id,
                week_number=day.week_number,
                day_number=day.day_number,
                day_name=day.day_name,
                workout_type=day.workout_type,
                exercises=day.exercises,
                target_muscles=day.target_muscles,
                estimated_duration_min=day.estimated_duration_min,
                estimated_calories=day.estimated_calories,
                notes=day.notes,
                is_rest_day=day.is_rest_day,
                is_completed=day.is_completed,
                completed_at=day.completed_at,
            )
            for day in sorted(plan.days, key=lambda d: (d.week_number, d.day_number))
        ],
    )


@router.get("/today", response_model=WorkoutPlanDayResponse | None)
async def get_todays_workout(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkoutPlanDayResponse | None:
    """Get the next scheduled workout from the active plan."""
    result = await db.execute(
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == current_user.id)
        .where(WorkoutPlan.is_active == True)
        .options(selectinload(WorkoutPlan.days))
        .order_by(WorkoutPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        return None

    # Find next incomplete non-rest day
    incomplete_days = [
        day for day in plan.days
        if not day.is_completed and not day.is_rest_day
    ]

    if not incomplete_days:
        return None

    # Sort and get next
    incomplete_days.sort(key=lambda d: (d.week_number, d.day_number))
    next_workout = incomplete_days[0]

    # Enrich exercises with images from ExerciseDB
    enriched_exercises = await enrich_exercises_with_images(next_workout.exercises or [])

    return WorkoutPlanDayResponse(
        id=next_workout.id,
        week_number=next_workout.week_number,
        day_number=next_workout.day_number,
        day_name=next_workout.day_name,
        workout_type=next_workout.workout_type,
        exercises=enriched_exercises,
        target_muscles=next_workout.target_muscles,
        estimated_duration_min=next_workout.estimated_duration_min,
        estimated_calories=next_workout.estimated_calories,
        notes=next_workout.notes,
        is_rest_day=next_workout.is_rest_day,
        is_completed=next_workout.is_completed,
        completed_at=next_workout.completed_at,
    )


# MARK: - Workout Plan Detail Endpoints

@router.get("/{plan_id}", response_model=WorkoutPlanResponse)
async def get_workout_plan(
    plan_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkoutPlanResponse:
    """Get a specific workout plan with all days."""
    result = await db.execute(
        select(WorkoutPlan)
        .where(WorkoutPlan.id == plan_id)
        .where(WorkoutPlan.user_id == current_user.id)
        .options(selectinload(WorkoutPlan.days))
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout plan not found",
        )

    return WorkoutPlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        duration_weeks=plan.duration_weeks,
        days_per_week=plan.days_per_week,
        goal=plan.goal,
        difficulty=plan.difficulty,
        equipment=plan.equipment,
        split_type=plan.split_type,
        is_active=plan.is_active,
        current_week=plan.current_week,
        current_day=plan.current_day,
        started_at=plan.started_at,
        created_at=plan.created_at,
        days=[
            WorkoutPlanDayResponse(
                id=day.id,
                week_number=day.week_number,
                day_number=day.day_number,
                day_name=day.day_name,
                workout_type=day.workout_type,
                exercises=day.exercises,
                target_muscles=day.target_muscles,
                estimated_duration_min=day.estimated_duration_min,
                estimated_calories=day.estimated_calories,
                notes=day.notes,
                is_rest_day=day.is_rest_day,
                is_completed=day.is_completed,
                completed_at=day.completed_at,
            )
            for day in sorted(plan.days, key=lambda d: (d.week_number, d.day_number))
        ],
    )


@router.delete("/{plan_id}")
async def delete_workout_plan(
    plan_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a workout plan."""
    result = await db.execute(
        select(WorkoutPlan)
        .where(WorkoutPlan.id == plan_id)
        .where(WorkoutPlan.user_id == current_user.id)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout plan not found",
        )

    await db.delete(plan)
    await db.commit()

    return {"success": True}


@router.patch("/{plan_id}/deactivate")
async def deactivate_workout_plan(
    plan_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Deactivate a workout plan."""
    result = await db.execute(
        select(WorkoutPlan)
        .where(WorkoutPlan.id == plan_id)
        .where(WorkoutPlan.user_id == current_user.id)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout plan not found",
        )

    plan.is_active = False
    await db.commit()

    return {"success": True}


@router.post("/{plan_id}/complete-day")
async def complete_workout_day(
    plan_id: str,
    request: MarkDayCompleteRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Mark a workout day as completed."""
    # Verify plan belongs to user
    result = await db.execute(
        select(WorkoutPlan)
        .where(WorkoutPlan.id == plan_id)
        .where(WorkoutPlan.user_id == current_user.id)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout plan not found",
        )

    # Get the workout day
    result = await db.execute(
        select(WorkoutPlanDay)
        .where(WorkoutPlanDay.id == request.workout_day_id)
        .where(WorkoutPlanDay.workout_plan_id == plan_id)
    )
    day = result.scalar_one_or_none()

    if not day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout day not found",
        )

    day.is_completed = True
    day.completed_at = datetime.utcnow()

    # Update plan's current position
    plan.current_week = day.week_number
    plan.current_day = day.day_number

    await db.commit()

    return {
        "success": True,
        "day_name": day.day_name,
        "week": day.week_number,
        "day": day.day_number,
    }


@router.get("/{plan_id}/week/{week_number}", response_model=list[WorkoutPlanDayResponse])
async def get_week_workouts(
    plan_id: str,
    week_number: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WorkoutPlanDayResponse]:
    """Get all workouts for a specific week."""
    result = await db.execute(
        select(WorkoutPlan)
        .where(WorkoutPlan.id == plan_id)
        .where(WorkoutPlan.user_id == current_user.id)
        .options(selectinload(WorkoutPlan.days))
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout plan not found",
        )

    week_days = [d for d in plan.days if d.week_number == week_number]
    week_days.sort(key=lambda d: d.day_number)

    return [
        WorkoutPlanDayResponse(
            id=day.id,
            week_number=day.week_number,
            day_number=day.day_number,
            day_name=day.day_name,
            workout_type=day.workout_type,
            exercises=day.exercises,
            target_muscles=day.target_muscles,
            estimated_duration_min=day.estimated_duration_min,
            estimated_calories=day.estimated_calories,
            notes=day.notes,
            is_rest_day=day.is_rest_day,
            is_completed=day.is_completed,
            completed_at=day.completed_at,
        )
        for day in week_days
    ]


# MARK: - Exercise Search Endpoint

@router.get("/exercises/search", response_model=list[ExerciseSearchResult])
async def search_exercises(
    query: str,
    muscle_group: str | None = None,
    equipment: str | None = None,
    limit: int = 20,
) -> list[ExerciseSearchResult]:
    """
    Search for exercises by name, muscle group, or equipment.

    Used for manual workout plan creation - returns exercises with
    GIF and video URLs for preview.
    """
    exercisedb = get_exercisedb_client()
    musclewiki = get_musclewiki_client()

    results = []

    # Search ExerciseDB first (primary source)
    db_result = await exercisedb.search_exercise(query)
    if db_result:
        # Try to get video from MuscleWiki
        mw_result = await musclewiki.search_exercise(query)

        results.append(ExerciseSearchResult(
            name=db_result.get("name", query),
            target_muscle=db_result.get("target_muscle"),
            secondary_muscles=db_result.get("secondary_muscles"),
            equipment=db_result.get("equipment"),
            gif_url=db_result.get("gif_url"),
            video_url=mw_result.get("video_url") if mw_result else None,
            instructions=db_result.get("instructions"),
        ))

    # If no ExerciseDB result, try MuscleWiki directly
    if not results:
        mw_result = await musclewiki.search_exercise(query)
        if mw_result:
            results.append(ExerciseSearchResult(
                name=mw_result.get("name", query),
                target_muscle=mw_result.get("target_muscles", [None])[0] if mw_result.get("target_muscles") else None,
                secondary_muscles=mw_result.get("secondary_muscles"),
                equipment=mw_result.get("equipment"),
                difficulty=mw_result.get("difficulty"),
                video_url=mw_result.get("video_url"),
                instructions=mw_result.get("instructions"),
            ))

    return results[:limit]


# MARK: - Manual Workout Plan Creation

class PlannedExerciseCreate(BaseModel):
    """Exercise data for manual plan creation."""
    name: str
    sets: int | None = None
    reps: str | None = None  # "8-12" or "10"
    weight_suggestion: str | None = None
    rest_sec: int | None = 60
    notes: str | None = None


class WorkoutPlanDayCreate(BaseModel):
    """Day data for manual plan creation."""
    week_number: int
    day_number: int
    day_name: str | None = None
    workout_type: str | None = None  # "push", "pull", "legs", etc.
    is_rest_day: bool = False
    exercises: list[PlannedExerciseCreate] = []
    target_muscles: list[str] | None = None
    notes: str | None = None


class WorkoutPlanCreate(BaseModel):
    """Request body for manual workout plan creation."""
    name: str
    description: str | None = None
    duration_weeks: int = 4
    days_per_week: int = 4
    goal: str | None = None  # "strength", "hypertrophy", "fat_loss"
    difficulty: str | None = None  # "beginner", "intermediate", "advanced"
    split_type: str | None = None  # "full_body", "upper_lower", "ppl"
    days: list[WorkoutPlanDayCreate] = []


@router.post("", response_model=WorkoutPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_workout_plan(
    plan_data: WorkoutPlanCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkoutPlanResponse:
    """
    Create a workout plan manually (bypassing AI generation).

    Used for the "Manual" tab in plan creation sheet.
    Exercises will be enriched with GIF/video URLs automatically.
    """
    import uuid

    # Deactivate any existing active plans
    result = await db.execute(
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == current_user.id)
        .where(WorkoutPlan.is_active == True)
    )
    existing_plans = result.scalars().all()
    for existing in existing_plans:
        existing.is_active = False

    # Create the new plan
    plan = WorkoutPlan(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=plan_data.name,
        description=plan_data.description,
        duration_weeks=plan_data.duration_weeks,
        days_per_week=plan_data.days_per_week,
        goal=plan_data.goal,
        difficulty=plan_data.difficulty,
        split_type=plan_data.split_type,
        is_active=True,
        current_week=1,
        current_day=1,
        started_at=datetime.utcnow(),
    )
    db.add(plan)

    # Create workout days with enriched exercises
    created_days = []
    for day_data in plan_data.days:
        # Convert exercises to dict format and enrich
        exercises = [ex.model_dump() for ex in day_data.exercises]
        enriched_exercises = await enrich_exercises_with_images(exercises)

        # Also try to add video URLs from MuscleWiki
        musclewiki = get_musclewiki_client()
        for ex in enriched_exercises:
            if not ex.get("video_url"):
                mw_result = await musclewiki.search_exercise(ex.get("name", ""))
                if mw_result:
                    ex["video_url"] = mw_result.get("video_url")

        day = WorkoutPlanDay(
            id=str(uuid.uuid4()),
            workout_plan_id=plan.id,
            week_number=day_data.week_number,
            day_number=day_data.day_number,
            day_name=day_data.day_name,
            workout_type=day_data.workout_type,
            exercises=enriched_exercises,
            target_muscles=day_data.target_muscles,
            is_rest_day=day_data.is_rest_day,
            is_completed=False,
            notes=day_data.notes,
            estimated_duration_min=len(enriched_exercises) * 5 if enriched_exercises else None,
        )
        db.add(day)
        created_days.append(day)

    await db.commit()
    await db.refresh(plan)

    return WorkoutPlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        duration_weeks=plan.duration_weeks,
        days_per_week=plan.days_per_week,
        goal=plan.goal,
        difficulty=plan.difficulty,
        equipment=plan.equipment,
        split_type=plan.split_type,
        is_active=plan.is_active,
        current_week=plan.current_week,
        current_day=plan.current_day,
        started_at=plan.started_at,
        created_at=plan.created_at,
        days=[
            WorkoutPlanDayResponse(
                id=day.id,
                week_number=day.week_number,
                day_number=day.day_number,
                day_name=day.day_name,
                workout_type=day.workout_type,
                exercises=day.exercises,
                target_muscles=day.target_muscles,
                estimated_duration_min=day.estimated_duration_min,
                estimated_calories=day.estimated_calories,
                notes=day.notes,
                is_rest_day=day.is_rest_day,
                is_completed=day.is_completed,
                completed_at=day.completed_at,
            )
            for day in sorted(created_days, key=lambda d: (d.week_number, d.day_number))
        ],
    )
