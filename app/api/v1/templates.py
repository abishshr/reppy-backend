"""Workout templates endpoints."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import WorkoutTemplate, get_db
from app.schemas.progress import (
    WorkoutTemplateCreate,
    WorkoutTemplateUpdate,
    WorkoutTemplateResponse,
)

router = APIRouter()


@router.get("/", response_model=list[WorkoutTemplateResponse])
async def list_templates(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_public: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[WorkoutTemplateResponse]:
    """List workout templates for the current user."""
    if include_public:
        # Include user's templates and public templates
        query = select(WorkoutTemplate).where(
            or_(
                WorkoutTemplate.user_id == current_user.id,
                WorkoutTemplate.is_public == True,
            )
        )
    else:
        query = select(WorkoutTemplate).where(
            WorkoutTemplate.user_id == current_user.id
        )

    result = await db.execute(
        query.order_by(WorkoutTemplate.times_used.desc()).limit(limit)
    )
    templates = result.scalars().all()
    return [WorkoutTemplateResponse.model_validate(t) for t in templates]


@router.post("/", response_model=WorkoutTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    current_user: CurrentUser,
    data: WorkoutTemplateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkoutTemplateResponse:
    """Create a new workout template."""
    template = WorkoutTemplate(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        workout_type=data.workout_type,
        exercises=data.exercises,
        estimated_duration_min=data.estimated_duration_min,
        target_muscles=data.target_muscles,
        is_public=data.is_public,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return WorkoutTemplateResponse.model_validate(template)


@router.get("/{template_id}", response_model=WorkoutTemplateResponse)
async def get_template(
    template_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkoutTemplateResponse:
    """Get a specific workout template."""
    result = await db.execute(
        select(WorkoutTemplate).where(
            WorkoutTemplate.id == template_id,
            or_(
                WorkoutTemplate.user_id == current_user.id,
                WorkoutTemplate.is_public == True,
            )
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return WorkoutTemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=WorkoutTemplateResponse)
async def update_template(
    template_id: str,
    data: WorkoutTemplateUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkoutTemplateResponse:
    """Update a workout template."""
    result = await db.execute(
        select(WorkoutTemplate).where(
            WorkoutTemplate.id == template_id,
            WorkoutTemplate.user_id == current_user.id,
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Update fields
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(template, field, value)

    await db.commit()
    await db.refresh(template)
    return WorkoutTemplateResponse.model_validate(template)


@router.post("/{template_id}/use", response_model=WorkoutTemplateResponse)
async def use_template(
    template_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkoutTemplateResponse:
    """Mark a template as used (increments usage counter)."""
    result = await db.execute(
        select(WorkoutTemplate).where(
            WorkoutTemplate.id == template_id,
            or_(
                WorkoutTemplate.user_id == current_user.id,
                WorkoutTemplate.is_public == True,
            )
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    template.times_used += 1
    template.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(template)
    return WorkoutTemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a workout template."""
    result = await db.execute(
        select(WorkoutTemplate).where(
            WorkoutTemplate.id == template_id,
            WorkoutTemplate.user_id == current_user.id,
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    await db.delete(template)
    await db.commit()
