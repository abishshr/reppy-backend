"""Body measurements endpoints."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import BodyMeasurement, get_db
from app.schemas.progress import BodyMeasurementCreate, BodyMeasurementResponse

router = APIRouter()


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
    """Log new body measurements."""
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
        body_fat_percentage=data.body_fat_percentage,
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
