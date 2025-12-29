"""Supplement tracking API endpoints."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.middleware.auth import get_current_user_id
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.models import Supplement, SupplementLog
from app.schemas.supplement import (
    SupplementCreate,
    SupplementUpdate,
    SupplementResponse,
    SupplementLogCreate,
    SupplementLogResponse,
    TodaySupplementSummary,
)
from app.services.streak import get_streak_service

router = APIRouter()


# ============================================================================
# Supplement CRUD Endpoints
# ============================================================================


@router.post("", response_model=SupplementResponse, status_code=status.HTTP_201_CREATED)
async def create_supplement(
    data: SupplementCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new supplement."""
    supplement = Supplement(
        user_id=user_id,
        name=data.name,
        brand=data.brand,
        serving_size=data.serving_size,
        notes=data.notes,
        # Vitamins
        vitamin_a_mcg=data.vitamin_a_mcg,
        vitamin_c_mg=data.vitamin_c_mg,
        vitamin_d_mcg=data.vitamin_d_mcg,
        vitamin_e_mg=data.vitamin_e_mg,
        vitamin_k_mcg=data.vitamin_k_mcg,
        vitamin_b1_mg=data.vitamin_b1_mg,
        vitamin_b2_mg=data.vitamin_b2_mg,
        vitamin_b3_mg=data.vitamin_b3_mg,
        vitamin_b6_mg=data.vitamin_b6_mg,
        vitamin_b9_mcg=data.vitamin_b9_mcg,
        vitamin_b12_mcg=data.vitamin_b12_mcg,
        # Minerals
        calcium_mg=data.calcium_mg,
        iron_mg=data.iron_mg,
        magnesium_mg=data.magnesium_mg,
        phosphorus_mg=data.phosphorus_mg,
        potassium_mg=data.potassium_mg,
        zinc_mg=data.zinc_mg,
        selenium_mcg=data.selenium_mcg,
        copper_mcg=data.copper_mcg,
        manganese_mg=data.manganese_mg,
        iodine_mcg=data.iodine_mcg,
        # Other
        omega3_mg=data.omega3_mg,
        biotin_mcg=data.biotin_mcg,
        choline_mg=data.choline_mg,
    )
    db.add(supplement)
    await db.commit()
    await db.refresh(supplement)
    return supplement


@router.get("", response_model=list[SupplementResponse])
async def list_supplements(
    active_only: bool = True,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List user's supplements."""
    query = select(Supplement).where(Supplement.user_id == user_id)
    if active_only:
        query = query.where(Supplement.is_active == True)
    query = query.order_by(Supplement.name)

    result = await db.execute(query)
    supplements = result.scalars().all()
    return supplements


@router.get("/{supplement_id}", response_model=SupplementResponse)
async def get_supplement(
    supplement_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific supplement."""
    result = await db.execute(
        select(Supplement).where(
            and_(Supplement.id == supplement_id, Supplement.user_id == user_id)
        )
    )
    supplement = result.scalar_one_or_none()
    if not supplement:
        raise HTTPException(status_code=404, detail="Supplement not found")
    return supplement


@router.patch("/{supplement_id}", response_model=SupplementResponse)
async def update_supplement(
    supplement_id: str,
    data: SupplementUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update a supplement."""
    result = await db.execute(
        select(Supplement).where(
            and_(Supplement.id == supplement_id, Supplement.user_id == user_id)
        )
    )
    supplement = result.scalar_one_or_none()
    if not supplement:
        raise HTTPException(status_code=404, detail="Supplement not found")

    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(supplement, field, value)

    supplement.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(supplement)
    return supplement


@router.delete("/{supplement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplement(
    supplement_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a supplement."""
    result = await db.execute(
        select(Supplement).where(
            and_(Supplement.id == supplement_id, Supplement.user_id == user_id)
        )
    )
    supplement = result.scalar_one_or_none()
    if not supplement:
        raise HTTPException(status_code=404, detail="Supplement not found")

    await db.delete(supplement)
    await db.commit()


# ============================================================================
# Supplement Logging Endpoints
# ============================================================================


@router.post("/log", response_model=SupplementLogResponse, status_code=status.HTTP_201_CREATED)
async def log_supplement(
    data: SupplementLogCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Log supplement intake."""
    # Verify supplement exists and belongs to user
    result = await db.execute(
        select(Supplement).where(
            and_(Supplement.id == data.supplement_id, Supplement.user_id == user_id)
        )
    )
    supplement = result.scalar_one_or_none()
    if not supplement:
        raise HTTPException(status_code=404, detail="Supplement not found")

    log = SupplementLog(
        user_id=user_id,
        supplement_id=data.supplement_id,
        servings=data.servings,
        logged_at=data.logged_at or datetime.utcnow(),
        notes=data.notes,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    # Update streak
    streak_service = get_streak_service(db)
    await streak_service.record_activity(user_id)

    # Calculate totals for response
    return SupplementLogResponse(
        id=log.id,
        user_id=log.user_id,
        supplement_id=log.supplement_id,
        supplement_name=supplement.name,
        servings=log.servings,
        logged_at=log.logged_at,
        notes=log.notes,
        created_at=log.created_at,
        total_vitamin_d_mcg=(supplement.vitamin_d_mcg or 0) * log.servings if supplement.vitamin_d_mcg else None,
        total_vitamin_c_mg=(supplement.vitamin_c_mg or 0) * log.servings if supplement.vitamin_c_mg else None,
        total_calcium_mg=(supplement.calcium_mg or 0) * log.servings if supplement.calcium_mg else None,
        total_iron_mg=(supplement.iron_mg or 0) * log.servings if supplement.iron_mg else None,
    )


@router.get("/logs/today", response_model=list[SupplementLogResponse])
async def get_today_logs(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get today's supplement logs."""
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())

    result = await db.execute(
        select(SupplementLog)
        .options(selectinload(SupplementLog.supplement))
        .where(
            and_(
                SupplementLog.user_id == user_id,
                SupplementLog.logged_at >= start_of_day,
                SupplementLog.logged_at <= end_of_day,
            )
        )
        .order_by(SupplementLog.logged_at.desc())
    )
    logs = result.scalars().all()

    return [
        SupplementLogResponse(
            id=log.id,
            user_id=log.user_id,
            supplement_id=log.supplement_id,
            supplement_name=log.supplement.name,
            servings=log.servings,
            logged_at=log.logged_at,
            notes=log.notes,
            created_at=log.created_at,
            total_vitamin_d_mcg=(log.supplement.vitamin_d_mcg or 0) * log.servings if log.supplement.vitamin_d_mcg else None,
            total_vitamin_c_mg=(log.supplement.vitamin_c_mg or 0) * log.servings if log.supplement.vitamin_c_mg else None,
            total_calcium_mg=(log.supplement.calcium_mg or 0) * log.servings if log.supplement.calcium_mg else None,
            total_iron_mg=(log.supplement.iron_mg or 0) * log.servings if log.supplement.iron_mg else None,
        )
        for log in logs
    ]


@router.get("/today", response_model=TodaySupplementSummary)
async def get_today_summary(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get today's supplement summary with totals."""
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())

    result = await db.execute(
        select(SupplementLog)
        .options(selectinload(SupplementLog.supplement))
        .where(
            and_(
                SupplementLog.user_id == user_id,
                SupplementLog.logged_at >= start_of_day,
                SupplementLog.logged_at <= end_of_day,
            )
        )
    )
    logs = result.scalars().all()

    # Calculate totals
    supplements_taken = list(set(log.supplement.name for log in logs))

    # Initialize totals
    totals = {
        "total_vitamin_a_mcg": 0.0,
        "total_vitamin_c_mg": 0.0,
        "total_vitamin_d_mcg": 0.0,
        "total_vitamin_e_mg": 0.0,
        "total_vitamin_k_mcg": 0.0,
        "total_vitamin_b1_mg": 0.0,
        "total_vitamin_b2_mg": 0.0,
        "total_vitamin_b3_mg": 0.0,
        "total_vitamin_b6_mg": 0.0,
        "total_vitamin_b9_mcg": 0.0,
        "total_vitamin_b12_mcg": 0.0,
        "total_calcium_mg": 0.0,
        "total_iron_mg": 0.0,
        "total_magnesium_mg": 0.0,
        "total_phosphorus_mg": 0.0,
        "total_potassium_mg": 0.0,
        "total_zinc_mg": 0.0,
        "total_selenium_mcg": 0.0,
        "total_copper_mcg": 0.0,
        "total_manganese_mg": 0.0,
    }

    # Sum up all nutrients from logged supplements
    for log in logs:
        supp = log.supplement
        servings = log.servings

        if supp.vitamin_a_mcg:
            totals["total_vitamin_a_mcg"] += supp.vitamin_a_mcg * servings
        if supp.vitamin_c_mg:
            totals["total_vitamin_c_mg"] += supp.vitamin_c_mg * servings
        if supp.vitamin_d_mcg:
            totals["total_vitamin_d_mcg"] += supp.vitamin_d_mcg * servings
        if supp.vitamin_e_mg:
            totals["total_vitamin_e_mg"] += supp.vitamin_e_mg * servings
        if supp.vitamin_k_mcg:
            totals["total_vitamin_k_mcg"] += supp.vitamin_k_mcg * servings
        if supp.vitamin_b1_mg:
            totals["total_vitamin_b1_mg"] += supp.vitamin_b1_mg * servings
        if supp.vitamin_b2_mg:
            totals["total_vitamin_b2_mg"] += supp.vitamin_b2_mg * servings
        if supp.vitamin_b3_mg:
            totals["total_vitamin_b3_mg"] += supp.vitamin_b3_mg * servings
        if supp.vitamin_b6_mg:
            totals["total_vitamin_b6_mg"] += supp.vitamin_b6_mg * servings
        if supp.vitamin_b9_mcg:
            totals["total_vitamin_b9_mcg"] += supp.vitamin_b9_mcg * servings
        if supp.vitamin_b12_mcg:
            totals["total_vitamin_b12_mcg"] += supp.vitamin_b12_mcg * servings
        if supp.calcium_mg:
            totals["total_calcium_mg"] += supp.calcium_mg * servings
        if supp.iron_mg:
            totals["total_iron_mg"] += supp.iron_mg * servings
        if supp.magnesium_mg:
            totals["total_magnesium_mg"] += supp.magnesium_mg * servings
        if supp.phosphorus_mg:
            totals["total_phosphorus_mg"] += supp.phosphorus_mg * servings
        if supp.potassium_mg:
            totals["total_potassium_mg"] += supp.potassium_mg * servings
        if supp.zinc_mg:
            totals["total_zinc_mg"] += supp.zinc_mg * servings
        if supp.selenium_mcg:
            totals["total_selenium_mcg"] += supp.selenium_mcg * servings
        if supp.copper_mcg:
            totals["total_copper_mcg"] += supp.copper_mcg * servings
        if supp.manganese_mg:
            totals["total_manganese_mg"] += supp.manganese_mg * servings

    return TodaySupplementSummary(
        total_logs=len(logs),
        supplements_taken=supplements_taken,
        **totals,
    )


@router.delete("/log/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplement_log(
    log_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a supplement log entry."""
    result = await db.execute(
        select(SupplementLog).where(
            and_(SupplementLog.id == log_id, SupplementLog.user_id == user_id)
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Supplement log not found")

    await db.delete(log)
    await db.commit()


@router.get("/logs/history", response_model=list[SupplementLogResponse])
async def get_supplement_history(
    days: int = 7,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get supplement log history for the past N days."""
    start_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(SupplementLog)
        .options(selectinload(SupplementLog.supplement))
        .where(
            and_(
                SupplementLog.user_id == user_id,
                SupplementLog.logged_at >= start_date,
            )
        )
        .order_by(SupplementLog.logged_at.desc())
    )
    logs = result.scalars().all()

    return [
        SupplementLogResponse(
            id=log.id,
            user_id=log.user_id,
            supplement_id=log.supplement_id,
            supplement_name=log.supplement.name,
            servings=log.servings,
            logged_at=log.logged_at,
            notes=log.notes,
            created_at=log.created_at,
            total_vitamin_d_mcg=(log.supplement.vitamin_d_mcg or 0) * log.servings if log.supplement.vitamin_d_mcg else None,
            total_vitamin_c_mg=(log.supplement.vitamin_c_mg or 0) * log.servings if log.supplement.vitamin_c_mg else None,
            total_calcium_mg=(log.supplement.calcium_mg or 0) * log.servings if log.supplement.calcium_mg else None,
            total_iron_mg=(log.supplement.iron_mg or 0) * log.servings if log.supplement.iron_mg else None,
        )
        for log in logs
    ]
