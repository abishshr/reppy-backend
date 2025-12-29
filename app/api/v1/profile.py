"""Profile management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import UserProfile, get_db
from app.schemas import ProfileCreate, ProfileResponse, ProfileUpdate

router = APIRouter()


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    """Get the current user's profile."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    # Calculate and persist targets if missing
    if not profile.daily_calorie_target and profile.weight_kg and profile.height_cm:
        profile_create = ProfileCreate(
            name=profile.name or "User",
            age=profile.age,
            sex=profile.sex,
            height_cm=profile.height_cm,
            weight_kg=profile.weight_kg,
            activity_level=profile.activity_level,
            goals=profile.goals or [],
        )
        daily_targets = calculate_daily_targets(profile_create)
        for field, value in daily_targets.items():
            setattr(profile, field, value)
        await db.commit()
        await db.refresh(profile)

    return ProfileResponse.model_validate(profile)


@router.post("/me", response_model=ProfileResponse)
async def create_profile(
    current_user: CurrentUser,
    profile_data: ProfileCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    """Create the current user's profile (during onboarding)."""
    # Check if profile already exists
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing profile
        for field, value in profile_data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)

        # Calculate daily targets if not already set
        if not existing.daily_calorie_target:
            daily_targets = calculate_daily_targets(profile_data)
            for field, value in daily_targets.items():
                setattr(existing, field, value)

        await db.commit()
        await db.refresh(existing)
        return ProfileResponse.model_validate(existing)

    # Calculate daily targets based on profile
    daily_targets = calculate_daily_targets(profile_data)

    profile = UserProfile(
        user_id=current_user.id,
        **profile_data.model_dump(),
        **daily_targets,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ProfileResponse.model_validate(profile)


@router.patch("/me", response_model=ProfileResponse)
async def update_profile(
    current_user: CurrentUser,
    profile_data: ProfileUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    """Update the current user's profile."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    # Update only provided fields
    update_data = profile_data.model_dump(exclude_unset=True)

    # If physical stats changed, recalculate targets
    physical_fields = {"weight_kg", "height_cm", "age", "sex", "activity_level", "goals"}
    if physical_fields & set(update_data.keys()):
        # Merge with existing values for calculation
        merged_data = ProfileCreate(
            name=profile.name or "User",
            age=update_data.get("age", profile.age),
            sex=update_data.get("sex", profile.sex),
            height_cm=update_data.get("height_cm", profile.height_cm),
            weight_kg=update_data.get("weight_kg", profile.weight_kg),
            activity_level=update_data.get("activity_level", profile.activity_level),
            goals=update_data.get("goals", profile.goals),
        )
        # Only update targets if not explicitly set
        if "daily_calorie_target" not in update_data:
            daily_targets = calculate_daily_targets(merged_data)
            update_data.update(daily_targets)

    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)

    return ProfileResponse.model_validate(profile)


def calculate_daily_targets(profile: ProfileCreate) -> dict:
    """
    Calculate daily macro targets based on profile.

    Uses Mifflin-St Jeor equation for BMR and activity multipliers.
    """
    if not all([profile.weight_kg, profile.height_cm, profile.age, profile.sex]):
        return {}

    # Mifflin-St Jeor equation
    if profile.sex == "male":
        bmr = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age + 5
    else:
        bmr = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age - 161

    # Activity multipliers
    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    multiplier = activity_multipliers.get(profile.activity_level or "moderate", 1.55)

    tdee = bmr * multiplier

    # Adjust based on goals
    goals = profile.goals or []
    if "fat_loss" in goals:
        calories = int(tdee * 0.8)  # 20% deficit
        protein_ratio = 0.35
        fat_ratio = 0.30
    elif "muscle_gain" in goals:
        calories = int(tdee * 1.1)  # 10% surplus
        protein_ratio = 0.30
        fat_ratio = 0.25
    else:
        calories = int(tdee)
        protein_ratio = 0.25
        fat_ratio = 0.30

    carb_ratio = 1 - protein_ratio - fat_ratio

    return {
        "daily_calorie_target": calories,
        "daily_protein_target": round(calories * protein_ratio / 4, 1),  # 4 cal/g
        "daily_carbs_target": round(calories * carb_ratio / 4, 1),
        "daily_fat_target": round(calories * fat_ratio / 9, 1),  # 9 cal/g
    }
