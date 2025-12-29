"""Body measurements endpoints."""

import math
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import BodyMeasurement, UserProfile, get_db
from app.schemas.progress import BodyMeasurementCreate, BodyMeasurementResponse

router = APIRouter()


def calculate_body_fat_us_navy(
    sex: str,
    height_cm: float,
    waist_cm: float,
    neck_cm: float,
    hips_cm: float | None = None,
) -> float | None:
    """
    Calculate body fat percentage using the US Navy method.

    For men: BF% = 495 / (1.0324 - 0.19077 * log10(waist - neck) + 0.15456 * log10(height)) - 450
    For women: BF% = 495 / (1.29579 - 0.35004 * log10(waist + hip - neck) + 0.22100 * log10(height)) - 450

    Args:
        sex: "male" or "female"
        height_cm: Height in centimeters
        waist_cm: Waist circumference in centimeters
        neck_cm: Neck circumference in centimeters
        hips_cm: Hip circumference in centimeters (required for females)

    Returns:
        Body fat percentage or None if calculation not possible
    """
    try:
        if sex == "male":
            if not all([height_cm, waist_cm, neck_cm]):
                return None
            if waist_cm <= neck_cm:
                return None

            body_fat = (
                495 / (
                    1.0324
                    - 0.19077 * math.log10(waist_cm - neck_cm)
                    + 0.15456 * math.log10(height_cm)
                ) - 450
            )
        else:  # female
            if not all([height_cm, waist_cm, neck_cm, hips_cm]):
                return None
            if (waist_cm + hips_cm) <= neck_cm:
                return None

            body_fat = (
                495 / (
                    1.29579
                    - 0.35004 * math.log10(waist_cm + hips_cm - neck_cm)
                    + 0.22100 * math.log10(height_cm)
                ) - 450
            )

        # Clamp to reasonable range
        body_fat = max(2.0, min(60.0, body_fat))
        return round(body_fat, 1)

    except (ValueError, ZeroDivisionError):
        return None


@router.get("/", response_model=list[BodyMeasurementResponse])
async def list_measurements(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[BodyMeasurementResponse]:
    """List body measurements for the current user."""
    result = await db.execute(
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == current_user.id)
        .order_by(BodyMeasurement.measured_at.desc())
        .limit(limit)
    )
    measurements = result.scalars().all()
    return [BodyMeasurementResponse.model_validate(m) for m in measurements]


@router.post("/", response_model=BodyMeasurementResponse, status_code=status.HTTP_201_CREATED)
async def create_measurement(
    current_user: CurrentUser,
    data: BodyMeasurementCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BodyMeasurementResponse:
    """Log new body measurements.

    If body_fat_percentage is not provided, it will be automatically calculated
    using the US Navy method (requires neck, waist, and hip measurements for females).
    """
    body_fat = data.body_fat_percentage

    # Auto-calculate body fat if not provided and we have the required measurements
    if body_fat is None and data.waist_cm and data.neck_cm:
        # Get user profile for height and sex
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == current_user.id)
        )
        profile = result.scalar_one_or_none()

        if profile and profile.height_cm and profile.sex:
            body_fat = calculate_body_fat_us_navy(
                sex=profile.sex,
                height_cm=profile.height_cm,
                waist_cm=data.waist_cm,
                neck_cm=data.neck_cm,
                hips_cm=data.hips_cm,
            )

    measurement = BodyMeasurement(
        user_id=current_user.id,
        measured_at=data.measured_at or datetime.now(timezone.utc),
        neck_cm=data.neck_cm,
        shoulders_cm=data.shoulders_cm,
        chest_cm=data.chest_cm,
        left_bicep_cm=data.left_bicep_cm,
        right_bicep_cm=data.right_bicep_cm,
        left_forearm_cm=data.left_forearm_cm,
        right_forearm_cm=data.right_forearm_cm,
        waist_cm=data.waist_cm,
        hips_cm=data.hips_cm,
        left_thigh_cm=data.left_thigh_cm,
        right_thigh_cm=data.right_thigh_cm,
        left_calf_cm=data.left_calf_cm,
        right_calf_cm=data.right_calf_cm,
        body_fat_percentage=body_fat,
        notes=data.notes,
    )
    db.add(measurement)
    await db.commit()
    await db.refresh(measurement)
    return BodyMeasurementResponse.model_validate(measurement)


@router.get("/latest", response_model=BodyMeasurementResponse)
async def get_latest_measurement(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BodyMeasurementResponse:
    """Get the most recent measurement."""
    result = await db.execute(
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == current_user.id)
        .order_by(BodyMeasurement.measured_at.desc())
        .limit(1)
    )
    measurement = result.scalar_one_or_none()
    if not measurement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No measurements found",
        )
    return BodyMeasurementResponse.model_validate(measurement)


@router.get("/compare")
async def compare_measurements(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Compare latest measurement with previous one."""
    result = await db.execute(
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == current_user.id)
        .order_by(BodyMeasurement.measured_at.desc())
        .limit(2)
    )
    measurements = result.scalars().all()

    if len(measurements) < 2:
        return {"message": "Need at least 2 measurements to compare", "comparisons": []}

    current = measurements[0]
    previous = measurements[1]

    fields = [
        "neck_cm", "shoulders_cm", "chest_cm", "left_bicep_cm", "right_bicep_cm",
        "left_forearm_cm", "right_forearm_cm", "waist_cm", "hips_cm",
        "left_thigh_cm", "right_thigh_cm", "left_calf_cm", "right_calf_cm",
        "body_fat_percentage"
    ]

    comparisons = []
    for field in fields:
        current_val = getattr(current, field)
        previous_val = getattr(previous, field)

        if current_val is not None and previous_val is not None:
            change = current_val - previous_val
            change_pct = (change / previous_val * 100) if previous_val != 0 else 0
            comparisons.append({
                "field": field,
                "current_value": current_val,
                "previous_value": previous_val,
                "change": round(change, 2),
                "change_percent": round(change_pct, 1),
            })

    return {
        "current_date": current.measured_at.isoformat(),
        "previous_date": previous.measured_at.isoformat(),
        "comparisons": comparisons,
    }


@router.post("/calculate-body-fat")
async def calculate_body_fat(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    waist_cm: float = Query(..., gt=0),
    neck_cm: float = Query(..., gt=0),
    hips_cm: float | None = Query(None, gt=0),
) -> dict:
    """
    Calculate body fat percentage without saving.

    Uses the US Navy method. Requires waist and neck measurements.
    Hip measurement is required for females.
    Uses height and sex from user profile.
    """
    # Get user profile for height and sex
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Complete onboarding first.",
        )

    if not profile.height_cm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Height is required in profile to calculate body fat.",
        )

    if not profile.sex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sex is required in profile to calculate body fat.",
        )

    if profile.sex == "female" and not hips_cm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hip measurement is required for females.",
        )

    body_fat = calculate_body_fat_us_navy(
        sex=profile.sex,
        height_cm=profile.height_cm,
        waist_cm=waist_cm,
        neck_cm=neck_cm,
        hips_cm=hips_cm,
    )

    if body_fat is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not calculate body fat. Check measurement values.",
        )

    # Provide category based on sex and body fat percentage
    if profile.sex == "male":
        if body_fat < 6:
            category = "Essential Fat"
        elif body_fat < 14:
            category = "Athletic"
        elif body_fat < 18:
            category = "Fitness"
        elif body_fat < 25:
            category = "Average"
        else:
            category = "Above Average"
    else:  # female
        if body_fat < 14:
            category = "Essential Fat"
        elif body_fat < 21:
            category = "Athletic"
        elif body_fat < 25:
            category = "Fitness"
        elif body_fat < 32:
            category = "Average"
        else:
            category = "Above Average"

    return {
        "body_fat_percentage": body_fat,
        "category": category,
        "method": "US Navy",
        "inputs": {
            "height_cm": profile.height_cm,
            "waist_cm": waist_cm,
            "neck_cm": neck_cm,
            "hips_cm": hips_cm,
            "sex": profile.sex,
        },
    }


@router.delete("/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurement(
    measurement_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a measurement."""
    result = await db.execute(
        select(BodyMeasurement)
        .where(BodyMeasurement.id == measurement_id)
        .where(BodyMeasurement.user_id == current_user.id)
    )
    measurement = result.scalar_one_or_none()

    if not measurement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Measurement not found",
        )

    await db.delete(measurement)
    await db.commit()
