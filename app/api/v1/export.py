"""Data export endpoints for CSV downloads."""

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import MealLog, WorkoutLog, WaterLog, get_db

router = APIRouter()


@router.get("/meals")
async def export_meals_csv(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365, description="Number of days to export"),
) -> StreamingResponse:
    """
    Export meal logs to CSV format.

    Returns a downloadable CSV file with all meals from the specified period.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == current_user.id)
        .where(MealLog.logged_at >= start_date)
        .order_by(MealLog.logged_at.desc())
    )
    meals = result.scalars().all()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Date",
        "Time",
        "Meal Type",
        "Food Items",
        "Calories",
        "Protein (g)",
        "Carbs (g)",
        "Fat (g)",
        "Fiber (g)",
        "Sugar (g)",
        "Notes",
    ])

    # Data rows
    for meal in meals:
        items_str = ", ".join([
            f"{item.get('name', 'Unknown')} ({item.get('quantity', 1)} {item.get('unit', 'serving')})"
            for item in (meal.items or [])
        ])

        writer.writerow([
            meal.logged_at.strftime("%Y-%m-%d"),
            meal.logged_at.strftime("%H:%M"),
            meal.meal_type or "Other",
            items_str,
            meal.calories or 0,
            round(meal.protein_g or 0, 1),
            round(meal.carbs_g or 0, 1),
            round(meal.fat_g or 0, 1),
            round(meal.fiber_g_est or 0, 1),
            round(meal.sugar_g_est or 0, 1),
            meal.notes or "",
        ])

    output.seek(0)

    filename = f"reppy_meals_{datetime.now().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/workouts")
async def export_workouts_csv(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365, description="Number of days to export"),
) -> StreamingResponse:
    """
    Export workout logs to CSV format.

    Returns a downloadable CSV file with all workouts from the specified period.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(WorkoutLog)
        .where(WorkoutLog.user_id == current_user.id)
        .where(WorkoutLog.logged_at >= start_date)
        .order_by(WorkoutLog.logged_at.desc())
    )
    workouts = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Date",
        "Time",
        "Workout Type",
        "Duration (min)",
        "Calories Burned",
        "Exercises",
        "Notes",
    ])

    # Data rows
    for workout in workouts:
        exercises_str = ", ".join([
            f"{ex.get('name', 'Unknown')}: {ex.get('sets', 0)}x{ex.get('reps', 0)}"
            + (f" @ {ex.get('weight_kg', 0)}kg" if ex.get('weight_kg') else "")
            for ex in (workout.exercises or [])
        ])

        writer.writerow([
            workout.logged_at.strftime("%Y-%m-%d"),
            workout.logged_at.strftime("%H:%M"),
            workout.workout_type or "Other",
            workout.duration_min or 0,
            workout.calories_burned_est or 0,
            exercises_str,
            workout.notes or "",
        ])

    output.seek(0)

    filename = f"reppy_workouts_{datetime.now().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/water")
async def export_water_csv(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365, description="Number of days to export"),
) -> StreamingResponse:
    """
    Export water logs to CSV format.

    Returns a downloadable CSV file with all water entries from the specified period.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(WaterLog)
        .where(WaterLog.user_id == current_user.id)
        .where(WaterLog.logged_at >= start_date)
        .order_by(WaterLog.logged_at.desc())
    )
    water_logs = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Date",
        "Time",
        "Amount (ml)",
        "Notes",
    ])

    # Data rows
    for log in water_logs:
        writer.writerow([
            log.logged_at.strftime("%Y-%m-%d"),
            log.logged_at.strftime("%H:%M"),
            log.amount_ml,
            log.notes or "",
        ])

    output.seek(0)

    filename = f"reppy_water_{datetime.now().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/all")
async def export_all_csv(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365, description="Number of days to export"),
) -> StreamingResponse:
    """
    Export all logs (meals, workouts, water) to a single CSV.

    Returns a downloadable CSV file with summary data for each day.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Get all data
    meals_result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == current_user.id)
        .where(MealLog.logged_at >= start_date)
    )
    meals = meals_result.scalars().all()

    workouts_result = await db.execute(
        select(WorkoutLog)
        .where(WorkoutLog.user_id == current_user.id)
        .where(WorkoutLog.logged_at >= start_date)
    )
    workouts = workouts_result.scalars().all()

    water_result = await db.execute(
        select(WaterLog)
        .where(WaterLog.user_id == current_user.id)
        .where(WaterLog.logged_at >= start_date)
    )
    water_logs = water_result.scalars().all()

    # Aggregate by day
    daily_data: dict[str, dict] = {}

    for meal in meals:
        date_key = meal.logged_at.strftime("%Y-%m-%d")
        if date_key not in daily_data:
            daily_data[date_key] = {
                "calories": 0,
                "protein": 0,
                "carbs": 0,
                "fat": 0,
                "meals": 0,
                "workouts": 0,
                "workout_duration": 0,
                "calories_burned": 0,
                "water_ml": 0,
            }
        daily_data[date_key]["calories"] += meal.calories or 0
        daily_data[date_key]["protein"] += meal.protein_g or 0
        daily_data[date_key]["carbs"] += meal.carbs_g or 0
        daily_data[date_key]["fat"] += meal.fat_g or 0
        daily_data[date_key]["meals"] += 1

    for workout in workouts:
        date_key = workout.logged_at.strftime("%Y-%m-%d")
        if date_key not in daily_data:
            daily_data[date_key] = {
                "calories": 0,
                "protein": 0,
                "carbs": 0,
                "fat": 0,
                "meals": 0,
                "workouts": 0,
                "workout_duration": 0,
                "calories_burned": 0,
                "water_ml": 0,
            }
        daily_data[date_key]["workouts"] += 1
        daily_data[date_key]["workout_duration"] += workout.duration_min or 0
        daily_data[date_key]["calories_burned"] += workout.calories_burned_est or 0

    for log in water_logs:
        date_key = log.logged_at.strftime("%Y-%m-%d")
        if date_key not in daily_data:
            daily_data[date_key] = {
                "calories": 0,
                "protein": 0,
                "carbs": 0,
                "fat": 0,
                "meals": 0,
                "workouts": 0,
                "workout_duration": 0,
                "calories_burned": 0,
                "water_ml": 0,
            }
        daily_data[date_key]["water_ml"] += log.amount_ml

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Date",
        "Meals",
        "Calories",
        "Protein (g)",
        "Carbs (g)",
        "Fat (g)",
        "Workouts",
        "Workout Duration (min)",
        "Calories Burned",
        "Water (ml)",
    ])

    # Data rows (sorted by date)
    for date_key in sorted(daily_data.keys(), reverse=True):
        data = daily_data[date_key]
        writer.writerow([
            date_key,
            data["meals"],
            data["calories"],
            round(data["protein"], 1),
            round(data["carbs"], 1),
            round(data["fat"], 1),
            data["workouts"],
            data["workout_duration"],
            data["calories_burned"],
            data["water_ml"],
        ])

    output.seek(0)

    filename = f"reppy_summary_{datetime.now().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
