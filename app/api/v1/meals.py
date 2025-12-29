"""Meal logging endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import MealLog, WorkoutLog, get_db
from app.infrastructure.database.models import UserProfile
from app.schemas import MealLogCreate, MealLogResponse
from app.schemas.meal import (
    DailyHealthSummary,
    MealHealthAnalysisResponse,
    MealSynergyResponse,
    SynergyInsight,
    TestosteroneSummaryResponse,
)
from app.services.health_score import analyze_meal_health, get_daily_health_summary
from app.services.nutrient_synergy import analyze_meal_synergies
from app.services.streak import get_streak_service
from app.services.testosterone_analyzer import testosterone_analyzer

router = APIRouter()


async def is_user_male(db: AsyncSession, user_id: str) -> bool:
    """Check if user is male for testosterone feature."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    return profile is not None and profile.sex == "male"


@router.get("/", response_model=list[MealLogResponse])
async def list_meals(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MealLogResponse]:
    """List recent meals for the current user."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == current_user.id)
        .where(MealLog.logged_at >= since)
        .order_by(MealLog.logged_at.desc())
        .limit(limit)
    )
    meals = result.scalars().all()

    return [MealLogResponse.model_validate(meal) for meal in meals]


@router.post("/", response_model=MealLogResponse, status_code=status.HTTP_201_CREATED)
async def create_meal(
    current_user: CurrentUser,
    meal_data: MealLogCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealLogResponse:
    """Log a new meal."""
    # Prepare items with testosterone impact for male users
    items_data = [item.model_dump() for item in meal_data.items]

    # Add testosterone impact for male users
    user_is_male = await is_user_male(db, current_user.id)
    if user_is_male:
        for item in items_data:
            impact = testosterone_analyzer.analyze_food(item.get("name", ""))
            item["testosterone_impact"] = impact

    meal = MealLog(
        user_id=current_user.id,
        logged_at=meal_data.logged_at or datetime.now(timezone.utc),
        meal_type=meal_data.meal_type,
        items=items_data,
        calories=meal_data.calories,
        protein_g=meal_data.protein_g,
        carbs_g=meal_data.carbs_g,
        fat_g=meal_data.fat_g,
        sugar_g_est=meal_data.sugar_g_est,
        fiber_g_est=meal_data.fiber_g_est,
        confidence=meal_data.confidence,
        notes=meal_data.notes,
        image_url=meal_data.image_url,
    )
    db.add(meal)
    await db.commit()
    await db.refresh(meal)

    # Update streak
    streak_service = get_streak_service(db)
    await streak_service.record_activity(current_user.id)

    # Build response with testosterone impact
    response = MealLogResponse.model_validate(meal)

    # Calculate overall meal testosterone impact for male users
    if user_is_male:
        response.testosterone_impact = testosterone_analyzer.analyze_meal(items_data)

    return response


@router.get("/{meal_id}", response_model=MealLogResponse)
async def get_meal(
    meal_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealLogResponse:
    """Get a specific meal by ID."""
    result = await db.execute(
        select(MealLog)
        .where(MealLog.id == meal_id)
        .where(MealLog.user_id == current_user.id)
    )
    meal = result.scalar_one_or_none()

    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found",
        )

    return MealLogResponse.model_validate(meal)


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(
    meal_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a meal log."""
    result = await db.execute(
        select(MealLog)
        .where(MealLog.id == meal_id)
        .where(MealLog.user_id == current_user.id)
    )
    meal = result.scalar_one_or_none()

    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found",
        )

    await db.delete(meal)
    await db.commit()


@router.post("/quick-add", response_model=MealLogResponse, status_code=status.HTTP_201_CREATED)
async def quick_add_calories(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    calories: int = Query(..., ge=1, le=10000, description="Calories to add"),
    description: str = Query(default="Quick Add", max_length=100),
    meal_type: str = Query(default="snack", regex="^(breakfast|lunch|dinner|snack)$"),
    protein_g: float | None = Query(default=None, ge=0, le=500),
    carbs_g: float | None = Query(default=None, ge=0, le=500),
    fat_g: float | None = Query(default=None, ge=0, le=500),
    logged_at: datetime | None = Query(default=None, description="Time the meal was eaten"),
) -> MealLogResponse:
    """
    Quick add calories without detailed meal items.

    Perfect for rough tracking or when eating out.
    """
    meal = MealLog(
        user_id=current_user.id,
        logged_at=logged_at or datetime.now(timezone.utc),
        meal_type=meal_type,
        items=[{"name": description, "quantity": 1, "unit": "serving"}],
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        confidence=0.5,  # Low confidence for quick add
        notes="Quick Add",
    )
    db.add(meal)
    await db.commit()
    await db.refresh(meal)

    return MealLogResponse.model_validate(meal)


@router.get("/recent-unique", response_model=list[MealLogResponse])
async def get_recent_unique_meals(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=7, ge=1, le=30),
    limit: int = Query(default=20, ge=1, le=50),
) -> list[MealLogResponse]:
    """
    Get recent unique meals for easy re-logging.

    Returns meals grouped by first item name, removing duplicates.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == current_user.id)
        .where(MealLog.logged_at >= since)
        .where(MealLog.notes != "Quick Add")  # Exclude quick adds
        .order_by(MealLog.logged_at.desc())
        .limit(limit * 3)  # Fetch extra to account for deduplication
    )
    meals = result.scalars().all()

    # Deduplicate by first item name
    seen = set()
    unique_meals = []
    for meal in meals:
        if meal.items:
            first_item = meal.items[0].get("name", "").lower()
            if first_item and first_item not in seen:
                seen.add(first_item)
                unique_meals.append(meal)
                if len(unique_meals) >= limit:
                    break

    return [MealLogResponse.model_validate(meal) for meal in unique_meals]


@router.post("/{meal_id}/copy", response_model=MealLogResponse, status_code=status.HTTP_201_CREATED)
async def copy_meal(
    meal_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    meal_type: str = Query(default=None, regex="^(breakfast|lunch|dinner|snack)$"),
) -> MealLogResponse:
    """
    Copy an existing meal to today.

    Optionally specify a different meal type.
    """
    # Get the original meal
    result = await db.execute(
        select(MealLog)
        .where(MealLog.id == meal_id)
        .where(MealLog.user_id == current_user.id)
    )
    original = result.scalar_one_or_none()

    if not original:
        raise HTTPException(status_code=404, detail="Meal not found")

    # Create copy with current timestamp
    copy = MealLog(
        user_id=current_user.id,
        logged_at=datetime.now(timezone.utc),
        meal_type=meal_type or original.meal_type,
        items=original.items,
        calories=original.calories,
        protein_g=original.protein_g,
        carbs_g=original.carbs_g,
        fat_g=original.fat_g,
        sugar_g_est=original.sugar_g_est,
        fiber_g_est=original.fiber_g_est,
        confidence=original.confidence,
        notes=f"Copied from {original.logged_at.strftime('%b %d')}",
        image_url=original.image_url,
    )
    db.add(copy)
    await db.commit()
    await db.refresh(copy)

    return MealLogResponse.model_validate(copy)


@router.get("/summary/today")
async def get_today_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get today's meal summary (totals) including exercise calories."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Get today's meals
    result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == current_user.id)
        .where(MealLog.logged_at >= today_start)
    )
    meals = result.scalars().all()

    # Get today's workouts for exercise calories
    workout_result = await db.execute(
        select(WorkoutLog)
        .where(WorkoutLog.user_id == current_user.id)
        .where(WorkoutLog.logged_at >= today_start)
    )
    workouts = workout_result.scalars().all()
    exercise_calories = sum(w.calories_burned_est or 0 for w in workouts)

    return {
        "date": today_start.date().isoformat(),
        "meal_count": len(meals),
        "total_calories": sum(m.calories or 0 for m in meals),
        "total_protein_g": sum(m.protein_g or 0 for m in meals),
        "total_carbs_g": sum(m.carbs_g or 0 for m in meals),
        "total_fat_g": sum(m.fat_g or 0 for m in meals),
        "total_sugar_g_est": sum(m.sugar_g_est or 0 for m in meals),
        "total_fiber_g_est": sum(m.fiber_g_est or 0 for m in meals),
        "total_sodium_mg_est": sum(m.sodium_mg_est or 0 for m in meals),
        "total_saturated_fat_g_est": sum(m.saturated_fat_g_est or 0 for m in meals),
        "total_cholesterol_mg_est": sum(m.cholesterol_mg_est or 0 for m in meals),
        "exercise_calories": exercise_calories,
        "workout_count": len(workouts),
    }


@router.get("/testosterone-summary/today", response_model=TestosteroneSummaryResponse)
async def get_testosterone_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TestosteroneSummaryResponse:
    """
    Get testosterone impact summary for today's meals.

    Only available for male users. Returns counts of boosting, reducing,
    and neutral foods consumed today, plus an overall rating.
    """
    # Check if user is male
    if not await is_user_male(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Testosterone tracking is only available for male users",
        )

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Get today's meals
    result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == current_user.id)
        .where(MealLog.logged_at >= today_start)
    )
    meals = result.scalars().all()

    # Count testosterone impacts from meal items
    boosting_count = 0
    reducing_count = 0
    neutral_count = 0

    for meal in meals:
        for item in meal.items or []:
            # Check if item already has testosterone_impact stored
            impact = item.get("testosterone_impact")
            if not impact:
                # Analyze on the fly if not stored
                impact = testosterone_analyzer.analyze_food(item.get("name", ""))

            if impact == "boosts":
                boosting_count += 1
            elif impact == "reduces":
                reducing_count += 1
            elif impact == "neutral":
                neutral_count += 1

    # Calculate overall rating
    if boosting_count > reducing_count * 2:
        overall_rating = "great"
    elif boosting_count > reducing_count:
        overall_rating = "good"
    elif reducing_count > boosting_count:
        overall_rating = "poor"
    else:
        overall_rating = "neutral"

    return TestosteroneSummaryResponse(
        boosting_count=boosting_count,
        reducing_count=reducing_count,
        neutral_count=neutral_count,
        overall_rating=overall_rating,
    )


@router.post("/{meal_id}/analyze-health", response_model=MealHealthAnalysisResponse)
async def analyze_meal_health_score(
    meal_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealHealthAnalysisResponse:
    """
    Analyze the health impact of a specific meal using AI.

    Returns a score from 0-100 with breakdown by nutritional balance,
    processing level, ingredient quality, and macro balance.
    """
    # Get the meal
    result = await db.execute(
        select(MealLog)
        .where(MealLog.id == meal_id)
        .where(MealLog.user_id == current_user.id)
    )
    meal = result.scalar_one_or_none()

    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found",
        )

    # Get user profile for dietary style
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()

    # Prepare meal items for analysis
    meal_items = meal.items or []

    # Add nutritional data
    for item in meal_items:
        item["total_calories"] = meal.calories
        item["total_protein_g"] = meal.protein_g
        item["total_carbs_g"] = meal.carbs_g
        item["total_fat_g"] = meal.fat_g

    # Get user goals if profile exists
    user_goals = None
    dietary_style = None
    if profile:
        dietary_style = profile.dietary_style
        user_goals = {
            "daily_calories": profile.daily_calorie_goal,
            "daily_protein_g": profile.daily_protein_goal_g,
            "daily_carbs_g": profile.daily_carbs_goal_g,
            "daily_fat_g": profile.daily_fat_goal_g,
        }

    # Analyze with AI
    analysis = await analyze_meal_health(meal_items, user_goals, dietary_style)

    return MealHealthAnalysisResponse(
        overall_score=analysis.overall_score,
        breakdown=analysis.breakdown,
        insights=analysis.insights,
        suggestions=analysis.suggestions,
        positive_aspects=analysis.positive_aspects,
        concerns=analysis.concerns,
    )


@router.get("/health-summary/today", response_model=DailyHealthSummary)
async def get_today_health_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DailyHealthSummary:
    """
    Get health summary for all meals logged today.

    Returns average health score and overall daily rating.
    """
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Get today's meals
    result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == current_user.id)
        .where(MealLog.logged_at >= today_start)
    )
    meals = result.scalars().all()

    # Convert to dicts for summary function
    meals_data = [
        {
            "id": m.id,
            "items": m.items,
            "calories": m.calories,
            "health_score": getattr(m, "health_score", None),
        }
        for m in meals
    ]

    # Get user goals
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()

    user_goals = None
    if profile:
        user_goals = {
            "daily_calories": profile.daily_calorie_goal,
        }

    summary = await get_daily_health_summary(meals_data, user_goals)

    return DailyHealthSummary(
        average_score=summary["average_score"],
        meal_count=summary.get("meal_count", 0),
        overall_rating=summary["overall_rating"],
        analyzed_at=datetime.fromisoformat(summary["analyzed_at"]),
    )


@router.get("/{meal_id}/synergy", response_model=MealSynergyResponse)
async def get_meal_synergies(
    meal_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealSynergyResponse:
    """
    Analyze nutrient synergies and interactions in a meal.

    Identifies beneficial combinations (e.g., iron + vitamin C) and
    inhibiting interactions (e.g., calcium + iron).
    """
    # Get the meal
    result = await db.execute(
        select(MealLog)
        .where(MealLog.id == meal_id)
        .where(MealLog.user_id == current_user.id)
    )
    meal = result.scalar_one_or_none()

    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found",
        )

    meal_items = meal.items or []
    insights = analyze_meal_synergies(meal_items)

    # Convert to response format
    response_insights = [
        SynergyInsight(
            type=i.type,
            title=i.title,
            description=i.description,
            foods_involved=i.foods_involved,
            impact=i.impact,
        )
        for i in insights
    ]

    beneficial_count = sum(1 for i in insights if i.type == "beneficial")
    inhibiting_count = sum(1 for i in insights if i.type == "inhibiting")

    return MealSynergyResponse(
        insights=response_insights,
        beneficial_count=beneficial_count,
        inhibiting_count=inhibiting_count,
    )
