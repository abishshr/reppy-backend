"""Progress tracking endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import get_current_user
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.models import (
    DailyActivity,
    MealLog,
    User,
    UserProfile,
    WeightLog,
    WorkoutLog,
)
from app.schemas.progress import (
    GoalPredictionResponse,
    GoalSettingsResponse,
    GoalSettingsUpdate,
    NutritionProgressResponse,
    ProgressSummaryResponse,
    StepsProgressResponse,
    WeightLogCreate,
    WeightLogResponse,
    WeightProgressResponse,
    WeightTrend,
    WorkoutProgressResponse,
)
from app.services.goal_prediction import predict_weight_goal

router = APIRouter()


@router.post("/weight", response_model=WeightLogResponse)
async def log_weight(
    data: WeightLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeightLogResponse:
    """Log a weight entry."""
    weight_log = WeightLog(
        user_id=current_user.id,
        weight_kg=data.weight_kg,
        logged_at=data.logged_at or datetime.now(timezone.utc),
        notes=data.notes,
        source=data.source,
    )
    db.add(weight_log)

    # Also update profile's current weight
    from sqlalchemy import select

    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile:
        profile.weight_kg = data.weight_kg

    await db.commit()
    await db.refresh(weight_log)

    return WeightLogResponse.model_validate(weight_log)


@router.get("/weight", response_model=list[WeightLogResponse])
async def get_weight_history(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WeightLogResponse]:
    """Get weight history for a period."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    from sqlalchemy import select

    result = await db.execute(
        select(WeightLog)
        .where(WeightLog.user_id == current_user.id)
        .where(WeightLog.logged_at >= since)
        .order_by(desc(WeightLog.logged_at))
    )
    logs = result.scalars().all()

    return [WeightLogResponse.model_validate(log) for log in logs]


@router.delete("/weight/{log_id}")
async def delete_weight_log(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete a weight log entry."""
    log = await db.get(WeightLog, log_id)
    if not log or log.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Weight log not found")

    await db.delete(log)
    await db.commit()
    return {"success": True}


@router.get("/weight/analytics", response_model=WeightProgressResponse)
async def get_weight_analytics(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeightProgressResponse:
    """Get weight progress analytics."""
    from sqlalchemy import select

    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(WeightLog)
        .where(WeightLog.user_id == current_user.id)
        .where(WeightLog.logged_at >= since)
        .order_by(WeightLog.logged_at)
    )
    logs = list(result.scalars().all())

    if not logs:
        return WeightProgressResponse(
            current_weight=None,
            starting_weight=None,
            lowest_weight=None,
            highest_weight=None,
            total_change=None,
            avg_weekly_change=None,
            trend=None,
            logs=[],
            days_tracked=0,
        )

    weights = [log.weight_kg for log in logs]
    current = weights[-1]
    starting = weights[0]
    total_change = current - starting

    # Calculate trend based on last 7 days vs previous 7 days
    recent_logs = [l for l in logs if l.logged_at >= datetime.now(timezone.utc) - timedelta(days=7)]
    older_logs = [
        l
        for l in logs
        if datetime.now(timezone.utc) - timedelta(days=14)
        <= l.logged_at
        < datetime.now(timezone.utc) - timedelta(days=7)
    ]

    trend = "maintaining"
    if recent_logs and older_logs:
        recent_avg = sum(l.weight_kg for l in recent_logs) / len(recent_logs)
        older_avg = sum(l.weight_kg for l in older_logs) / len(older_logs)
        diff = recent_avg - older_avg
        if diff < -0.3:
            trend = "losing"
        elif diff > 0.3:
            trend = "gaining"

    # Calculate days tracked
    first_log = logs[0].logged_at
    last_log = logs[-1].logged_at
    days_tracked = (last_log - first_log).days + 1

    # Average weekly change
    weeks = max(1, days_tracked / 7)
    avg_weekly_change = total_change / weeks

    return WeightProgressResponse(
        current_weight=current,
        starting_weight=starting,
        lowest_weight=min(weights),
        highest_weight=max(weights),
        total_change=round(total_change, 2),
        avg_weekly_change=round(avg_weekly_change, 2),
        trend=trend,
        logs=[WeightTrend(date=log.logged_at, weight_kg=log.weight_kg) for log in logs],
        days_tracked=days_tracked,
    )


@router.get("/workouts/analytics", response_model=WorkoutProgressResponse)
async def get_workout_analytics(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkoutProgressResponse:
    """Get workout progress analytics."""
    from sqlalchemy import select

    since = datetime.now(timezone.utc) - timedelta(days=days)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # Get all workouts in period
    result = await db.execute(
        select(WorkoutLog)
        .where(WorkoutLog.user_id == current_user.id)
        .where(WorkoutLog.logged_at >= since)
        .order_by(desc(WorkoutLog.logged_at))
    )
    workouts = list(result.scalars().all())

    # This week/month counts
    this_week = len([w for w in workouts if w.logged_at >= week_ago])
    this_month = len([w for w in workouts if w.logged_at >= month_ago])

    # Total duration
    total_duration = sum(w.duration_min or 0 for w in workouts)
    avg_duration = total_duration / len(workouts) if workouts else 0

    # Favorite workout type
    type_counts: dict[str, int] = {}
    for w in workouts:
        if w.workout_type:
            type_counts[w.workout_type] = type_counts.get(w.workout_type, 0) + 1
    favorite_type = max(type_counts, key=type_counts.get) if type_counts else None

    # Calculate streaks
    current_streak = 0
    longest_streak = 0

    if workouts:
        # Get unique workout dates
        workout_dates = set()
        for w in workouts:
            workout_dates.add(w.logged_at.date())

        # Calculate current streak (consecutive days from today)
        today = datetime.now(timezone.utc).date()
        streak_date = today
        while streak_date in workout_dates or (
            streak_date == today and today not in workout_dates
        ):
            if streak_date in workout_dates:
                current_streak += 1
            streak_date -= timedelta(days=1)
            if streak_date not in workout_dates and streak_date != today:
                break

        # Calculate longest streak
        sorted_dates = sorted(workout_dates)
        temp_streak = 1
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
                temp_streak += 1
                longest_streak = max(longest_streak, temp_streak)
            else:
                temp_streak = 1
        longest_streak = max(longest_streak, temp_streak) if sorted_dates else 0

    return WorkoutProgressResponse(
        total_workouts=len(workouts),
        workouts_this_week=this_week,
        workouts_this_month=this_month,
        current_streak=current_streak,
        longest_streak=longest_streak,
        total_duration_min=total_duration,
        avg_workout_duration_min=round(avg_duration, 1),
        favorite_workout_type=favorite_type,
    )


@router.get("/nutrition/analytics", response_model=NutritionProgressResponse)
async def get_nutrition_analytics(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NutritionProgressResponse:
    """Get nutrition progress analytics."""
    from sqlalchemy import select

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get all meals in period
    result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == current_user.id)
        .where(MealLog.logged_at >= since)
        .order_by(MealLog.logged_at)
    )
    meals = list(result.scalars().all())

    if not meals:
        return NutritionProgressResponse(
            avg_daily_calories=0,
            avg_daily_protein=0,
            avg_daily_carbs=0,
            avg_daily_fat=0,
            days_on_target=0,
            days_over_target=0,
            days_under_target=0,
            total_meals_logged=0,
        )

    # Get user's targets
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    calorie_target = profile.daily_calorie_target if profile else 2000

    # Group meals by date and calculate daily totals
    daily_totals: dict[str, dict] = {}
    for meal in meals:
        date_key = meal.logged_at.date().isoformat()
        if date_key not in daily_totals:
            daily_totals[date_key] = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
        daily_totals[date_key]["calories"] += meal.calories or 0
        daily_totals[date_key]["protein"] += meal.protein_g or 0
        daily_totals[date_key]["carbs"] += meal.carbs_g or 0
        daily_totals[date_key]["fat"] += meal.fat_g or 0

    num_days = len(daily_totals)
    total_calories = sum(d["calories"] for d in daily_totals.values())
    total_protein = sum(d["protein"] for d in daily_totals.values())
    total_carbs = sum(d["carbs"] for d in daily_totals.values())
    total_fat = sum(d["fat"] for d in daily_totals.values())

    # Count days on/over/under target (within 10% is on target)
    days_on_target = 0
    days_over = 0
    days_under = 0
    tolerance = calorie_target * 0.1

    for daily in daily_totals.values():
        if abs(daily["calories"] - calorie_target) <= tolerance:
            days_on_target += 1
        elif daily["calories"] > calorie_target:
            days_over += 1
        else:
            days_under += 1

    return NutritionProgressResponse(
        avg_daily_calories=round(total_calories / num_days, 1) if num_days else 0,
        avg_daily_protein=round(total_protein / num_days, 1) if num_days else 0,
        avg_daily_carbs=round(total_carbs / num_days, 1) if num_days else 0,
        avg_daily_fat=round(total_fat / num_days, 1) if num_days else 0,
        days_on_target=days_on_target,
        days_over_target=days_over,
        days_under_target=days_under,
        total_meals_logged=len(meals),
    )


@router.get("/steps/analytics", response_model=StepsProgressResponse)
async def get_steps_analytics(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StepsProgressResponse:
    """Get steps progress analytics."""
    from sqlalchemy import select

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get all activity logs in period
    result = await db.execute(
        select(DailyActivity)
        .where(DailyActivity.user_id == current_user.id)
        .where(DailyActivity.date >= since)
        .order_by(desc(DailyActivity.date))
    )
    activities = list(result.scalars().all())

    # Get user's step goal
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    step_goal = profile.daily_steps_goal if profile else 10000

    if not activities:
        return StepsProgressResponse(
            avg_daily_steps=0,
            total_steps=0,
            days_goal_met=0,
            current_streak=0,
            best_day_steps=0,
        )

    steps_list = [a.steps or 0 for a in activities]
    total_steps = sum(steps_list)
    avg_steps = total_steps // len(steps_list) if steps_list else 0
    best_day = max(steps_list) if steps_list else 0
    days_goal_met = len([s for s in steps_list if s >= step_goal])

    # Calculate current streak
    current_streak = 0
    for activity in activities:
        if (activity.steps or 0) >= step_goal:
            current_streak += 1
        else:
            break

    return StepsProgressResponse(
        avg_daily_steps=avg_steps,
        total_steps=total_steps,
        days_goal_met=days_goal_met,
        current_streak=current_streak,
        best_day_steps=best_day,
    )


@router.get("/summary", response_model=ProgressSummaryResponse)
async def get_progress_summary(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProgressSummaryResponse:
    """Get complete progress summary."""
    weight = await get_weight_analytics(days, db, current_user)
    workouts = await get_workout_analytics(days, db, current_user)
    nutrition = await get_nutrition_analytics(days, db, current_user)
    steps = await get_steps_analytics(days, db, current_user)

    return ProgressSummaryResponse(
        weight=weight if weight.logs else None,
        workouts=workouts,
        nutrition=nutrition,
        steps=steps,
        period_days=days,
    )


# =============================================================================
# Goal Timeline Prediction
# =============================================================================


@router.get("/weight/goal-settings", response_model=GoalSettingsResponse)
async def get_goal_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalSettingsResponse:
    """Get current weight goal settings."""
    from sqlalchemy import select

    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return GoalSettingsResponse(
            weight_goal_kg=None,
            target_rate_kg_per_week=None,
            goal_target_date=None,
        )

    return GoalSettingsResponse(
        weight_goal_kg=profile.weight_goal_kg,
        target_rate_kg_per_week=profile.target_rate_kg_per_week,
        goal_target_date=profile.goal_target_date,
    )


@router.patch("/weight/goal-settings", response_model=GoalSettingsResponse)
async def update_goal_settings(
    data: GoalSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalSettingsResponse:
    """Update weight goal settings."""
    from sqlalchemy import select

    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Update only provided fields
    if data.weight_goal_kg is not None:
        profile.weight_goal_kg = data.weight_goal_kg
    if data.target_rate_kg_per_week is not None:
        profile.target_rate_kg_per_week = data.target_rate_kg_per_week
    if data.goal_target_date is not None:
        profile.goal_target_date = data.goal_target_date

    await db.commit()
    await db.refresh(profile)

    return GoalSettingsResponse(
        weight_goal_kg=profile.weight_goal_kg,
        target_rate_kg_per_week=profile.target_rate_kg_per_week,
        goal_target_date=profile.goal_target_date,
    )


@router.delete("/weight/goal-settings")
async def clear_goal_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Clear weight goal settings."""
    from sqlalchemy import select

    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if profile:
        profile.weight_goal_kg = None
        profile.target_rate_kg_per_week = None
        profile.goal_target_date = None
        await db.commit()

    return {"success": True}


@router.get("/weight/prediction", response_model=GoalPredictionResponse)
async def get_weight_prediction(
    days: int = Query(90, ge=30, le=365, description="Days of history to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalPredictionResponse:
    """
    Get weight goal timeline prediction.

    Uses linear regression on weight history to predict when you'll reach your goal.
    """
    from sqlalchemy import select

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get weight logs
    result = await db.execute(
        select(WeightLog)
        .where(WeightLog.user_id == current_user.id)
        .where(WeightLog.logged_at >= since)
        .order_by(WeightLog.logged_at)
    )
    logs = list(result.scalars().all())

    # Get profile for goal settings
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()

    # Build weight log tuples
    weight_logs = [(log.logged_at, log.weight_kg) for log in logs]

    # Get current weight (most recent log or profile)
    current_weight = logs[-1].weight_kg if logs else (profile.weight_kg if profile else None)

    # Get goal settings
    goal_weight = profile.weight_goal_kg if profile else None
    target_rate = profile.target_rate_kg_per_week if profile else None
    goal_date = profile.goal_target_date if profile else None

    # Get starting weight (first log in period)
    starting_weight = logs[0].weight_kg if logs else None

    return predict_weight_goal(
        weight_logs=weight_logs,
        current_weight=current_weight,
        goal_weight=goal_weight,
        target_rate_kg_per_week=target_rate,
        goal_target_date=goal_date,
        starting_weight=starting_weight,
    )
