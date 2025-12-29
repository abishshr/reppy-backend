"""Progress photos endpoints."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import ProgressPhoto, get_db
from app.schemas.progress import ProgressPhotoCreate, ProgressPhotoResponse

router = APIRouter()


@router.get("/", response_model=list[ProgressPhotoResponse])
async def list_photos(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    photo_type: str | None = Query(None, pattern="^(front|side|back)$"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ProgressPhotoResponse]:
    """List progress photos for the current user."""
    query = select(ProgressPhoto).where(ProgressPhoto.user_id == current_user.id)

    if photo_type:
        query = query.where(ProgressPhoto.photo_type == photo_type)

    result = await db.execute(
        query.order_by(ProgressPhoto.taken_at.desc()).limit(limit)
    )
    photos = result.scalars().all()
    return [ProgressPhotoResponse.model_validate(p) for p in photos]


@router.post("/", response_model=ProgressPhotoResponse, status_code=status.HTTP_201_CREATED)
async def create_photo(
    current_user: CurrentUser,
    data: ProgressPhotoCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProgressPhotoResponse:
    """Upload a new progress photo."""
    photo = ProgressPhoto(
        user_id=current_user.id,
        photo_url=data.photo_url,
        thumbnail_url=data.thumbnail_url,
        photo_type=data.photo_type,
        weight_kg=data.weight_kg,
        notes=data.notes,
        taken_at=data.taken_at or datetime.now(timezone.utc),
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return ProgressPhotoResponse.model_validate(photo)


@router.get("/compare")
async def compare_photos(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    photo_type: str = Query(default="front", pattern="^(front|side|back)$"),
) -> dict:
    """Get earliest and latest photos for comparison."""
    # Get earliest
    earliest_result = await db.execute(
        select(ProgressPhoto)
        .where(
            ProgressPhoto.user_id == current_user.id,
            ProgressPhoto.photo_type == photo_type,
        )
        .order_by(ProgressPhoto.taken_at.asc())
        .limit(1)
    )
    earliest = earliest_result.scalar_one_or_none()

    # Get latest
    latest_result = await db.execute(
        select(ProgressPhoto)
        .where(
            ProgressPhoto.user_id == current_user.id,
            ProgressPhoto.photo_type == photo_type,
        )
        .order_by(ProgressPhoto.taken_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()

    if not earliest or not latest or earliest.id == latest.id:
        return {"message": "Need at least 2 photos to compare", "comparison": None}

    return {
        "earliest": ProgressPhotoResponse.model_validate(earliest),
        "latest": ProgressPhotoResponse.model_validate(latest),
        "days_between": (latest.taken_at - earliest.taken_at).days,
        "weight_change_kg": (
            round(latest.weight_kg - earliest.weight_kg, 1)
            if latest.weight_kg and earliest.weight_kg
            else None
        ),
    }


@router.get("/{photo_id}", response_model=ProgressPhotoResponse)
async def get_photo(
    photo_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProgressPhotoResponse:
    """Get a specific progress photo."""
    result = await db.execute(
        select(ProgressPhoto).where(
            ProgressPhoto.id == photo_id,
            ProgressPhoto.user_id == current_user.id,
        )
    )
    photo = result.scalar_one_or_none()

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )

    return ProgressPhotoResponse.model_validate(photo)


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(
    photo_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a progress photo."""
    result = await db.execute(
        select(ProgressPhoto).where(
            ProgressPhoto.id == photo_id,
            ProgressPhoto.user_id == current_user.id,
        )
    )
    photo = result.scalar_one_or_none()

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )

    await db.delete(photo)
    await db.commit()
