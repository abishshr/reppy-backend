"""Circadian rhythm and meal timing endpoints."""

from datetime import datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import MealLog, get_db
from app.schemas.circadian import (
    CircadianAnalysisResponse,
    CircadianRecommendation,
    MealTimingAnalysisResponse,
    OptimalMealTimesRequest,
    OptimalMealTimesResponse,
)
from app.services.circadian_optimizer import (
    analyze_meal_timing,
    get_circadian_recommendations,
    get_optimal_meal_times,
)

router = APIRouter()


@router.get("/analysis", response_model=CircadianAnalysisResponse)
async def get_circadian_analysis(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=14, ge=7, le=90, description="Days of data to analyze"),
) -> CircadianAnalysisResponse:
    """
    Analyze meal timing patterns and circadian rhythm alignment.

    Returns analysis of eating window, consistency, late-night eating
    frequency, and personalized recommendations.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get meal logs for the period
    result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == current_user.id)
        .where(MealLog.logged_at >= since)
        .order_by(MealLog.logged_at)
    )
    meals = result.scalars().all()

    if not meals:
        return CircadianAnalysisResponse(
            analysis=MealTimingAnalysisResponse(
                average_first_meal=None,
                average_last_meal=None,
                eating_window_hours=None,
                late_night_eating_frequency=0,
                consistency_score=0,
                meal_time_variance_minutes=0,
            ),
            recommendations=[],
            has_data=False,
        )

    # Convert to dicts for analysis
    meal_logs = [
        {"logged_at": m.logged_at, "meal_type": m.meal_type}
        for m in meals
    ]

    # Perform analysis
    analysis = analyze_meal_timing(meal_logs)

    # Get recommendations
    recommendations = get_circadian_recommendations(analysis)

    # Convert to response format
    analysis_response = MealTimingAnalysisResponse(
        average_first_meal=analysis.average_first_meal.strftime("%H:%M") if analysis.average_first_meal else None,
        average_last_meal=analysis.average_last_meal.strftime("%H:%M") if analysis.average_last_meal else None,
        eating_window_hours=analysis.eating_window_hours,
        late_night_eating_frequency=analysis.late_night_eating_frequency,
        consistency_score=analysis.consistency_score,
        meal_time_variance_minutes=analysis.meal_time_variance_minutes,
    )

    recommendation_responses = [
        CircadianRecommendation(
            priority=r.priority,
            title=r.title,
            description=r.description,
            action=r.action,
            benefit=r.benefit,
        )
        for r in recommendations
    ]

    return CircadianAnalysisResponse(
        analysis=analysis_response,
        recommendations=recommendation_responses,
        has_data=True,
    )


@router.get("/recommendations", response_model=list[CircadianRecommendation])
async def get_recommendations_only(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=14, ge=7, le=90),
) -> list[CircadianRecommendation]:
    """
    Get circadian recommendations without full analysis.

    Useful for quick display in dashboards or notifications.
    """
    result = await get_circadian_analysis(current_user, db, days)
    return result.recommendations


@router.post("/optimal-times", response_model=OptimalMealTimesResponse)
async def calculate_optimal_times(
    request: OptimalMealTimesRequest,
    current_user: CurrentUser,
) -> OptimalMealTimesResponse:
    """
    Calculate optimal meal times based on sleep schedule.

    Provides personalized meal timing recommendations based on
    circadian rhythm principles and the user's wake/sleep times.
    """
    # Parse times
    wake_parts = request.wake_time.split(":")
    sleep_parts = request.sleep_time.split(":")

    wake_time = time(int(wake_parts[0]), int(wake_parts[1]))
    sleep_time = time(int(sleep_parts[0]), int(sleep_parts[1]))

    # Get optimal times
    optimal = get_optimal_meal_times(wake_time, sleep_time)

    return OptimalMealTimesResponse(
        breakfast=optimal["breakfast"],
        lunch=optimal["lunch"],
        dinner=optimal["dinner"],
        eating_cutoff=optimal["eating_cutoff"],
        eating_window_hours=optimal["eating_window_hours"],
    )


@router.get("/eating-window")
async def get_eating_window_stats(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=7, ge=1, le=30),
) -> dict:
    """
    Get daily eating window statistics.

    Returns first meal, last meal, and eating window duration
    for each day in the specified period.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == current_user.id)
        .where(MealLog.logged_at >= since)
        .order_by(MealLog.logged_at)
    )
    meals = result.scalars().all()

    # Group by date
    daily_windows: dict[str, dict] = {}

    for meal in meals:
        date_key = meal.logged_at.date().isoformat()

        if date_key not in daily_windows:
            daily_windows[date_key] = {
                "date": date_key,
                "first_meal": meal.logged_at.isoformat(),
                "last_meal": meal.logged_at.isoformat(),
                "meal_count": 0,
            }

        daily_windows[date_key]["last_meal"] = meal.logged_at.isoformat()
        daily_windows[date_key]["meal_count"] += 1

    # Calculate eating windows
    windows = []
    for date_key, data in sorted(daily_windows.items()):
        first = datetime.fromisoformat(data["first_meal"])
        last = datetime.fromisoformat(data["last_meal"])
        window_hours = (last - first).total_seconds() / 3600

        windows.append({
            "date": data["date"],
            "first_meal": first.strftime("%H:%M"),
            "last_meal": last.strftime("%H:%M"),
            "eating_window_hours": round(window_hours, 1),
            "meal_count": data["meal_count"],
        })

    # Calculate averages
    avg_window = sum(w["eating_window_hours"] for w in windows) / len(windows) if windows else 0

    return {
        "daily_windows": windows,
        "average_eating_window_hours": round(avg_window, 1),
        "days_analyzed": len(windows),
    }
