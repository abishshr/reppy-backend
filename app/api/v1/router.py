"""Main API router combining all v1 routes."""

from fastapi import APIRouter

from app.api.v1 import (
    achievements,
    activity,
    auth,
    blood_work,
    challenges,
    chat,
    circadian,
    cycle,
    export,
    fasting,
    foods,
    meal_plans,
    meals,
    measurements,
    photos,
    profile,
    progress,
    social,
    streak,
    supplements,
    templates,
    water,
    workout_plans,
    workouts,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(meals.router, prefix="/meals", tags=["meals"])
api_router.include_router(workouts.router, prefix="/workouts", tags=["workouts"])
api_router.include_router(activity.router, prefix="/activity", tags=["activity"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(meal_plans.router, prefix="/meal-plans", tags=["meal-plans"])
api_router.include_router(workout_plans.router, prefix="/workout-plans", tags=["workout-plans"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(water.router, prefix="/water", tags=["water"])
api_router.include_router(foods.router, prefix="/foods", tags=["foods"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(streak.router, prefix="/streak", tags=["streak"])
api_router.include_router(photos.router, prefix="/photos", tags=["photos"])
api_router.include_router(measurements.router, prefix="/measurements", tags=["measurements"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(achievements.router, prefix="/achievements", tags=["achievements"])
api_router.include_router(challenges.router, prefix="/challenges", tags=["challenges"])
api_router.include_router(social.router, prefix="/social", tags=["social"])
api_router.include_router(cycle.router, prefix="/cycle", tags=["cycle"])
api_router.include_router(fasting.router, prefix="/fasting", tags=["fasting"])
api_router.include_router(circadian.router, prefix="/circadian", tags=["circadian"])
api_router.include_router(supplements.router, prefix="/supplements", tags=["supplements"])
api_router.include_router(blood_work.router, prefix="/blood-work", tags=["blood-work"])
