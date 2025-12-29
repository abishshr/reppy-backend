"""Blood work tracking API endpoints."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import get_current_user_id
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.models import BloodWorkPanel
from app.schemas.blood_work import (
    BloodWorkPanelCreate,
    BloodWorkPanelUpdate,
    BloodWorkPanelResponse,
    BloodWorkOCRRequest,
    BloodWorkOCRResponse,
    BloodWorkConfirmOCRRequest,
    BloodWorkAnalysisResponse,
    ApplyRecommendationsRequest,
    ApplyRecommendationsResponse,
    BloodWorkTrendResponse,
    BloodWorkSummary,
    BloodMarkerResult,
    MarkerStatus,
    REFERENCE_RANGES,
    TrendDataPoint,
)

router = APIRouter()


# =============================================================================
# Helper Functions
# =============================================================================


def classify_marker_status(value: float, marker_key: str) -> MarkerStatus:
    """Classify a marker value as low/suboptimal/optimal/high."""
    ref = REFERENCE_RANGES.get(marker_key)
    if not ref:
        return MarkerStatus.OPTIMAL

    if value < ref.low:
        return MarkerStatus.LOW
    elif value > ref.high:
        return MarkerStatus.HIGH
    elif ref.optimal_low and ref.optimal_high:
        if value < ref.optimal_low:
            return MarkerStatus.SUBOPTIMAL_LOW
        elif value > ref.optimal_high:
            return MarkerStatus.SUBOPTIMAL_HIGH
        else:
            return MarkerStatus.OPTIMAL
    else:
        return MarkerStatus.OPTIMAL


def get_marker_result(panel: BloodWorkPanel, marker_key: str) -> BloodMarkerResult | None:
    """Get a BloodMarkerResult for a specific marker if it has a value."""
    value = getattr(panel, marker_key, None)
    if value is None:
        return None

    ref = REFERENCE_RANGES.get(marker_key)
    if not ref:
        return None

    return BloodMarkerResult(
        marker_key=marker_key,
        name=ref.name,
        value=value,
        unit=ref.unit,
        status=classify_marker_status(value, marker_key),
        reference_low=ref.low,
        reference_high=ref.high,
        optimal_low=ref.optimal_low,
        optimal_high=ref.optimal_high,
    )


# =============================================================================
# CRUD Endpoints
# =============================================================================


@router.post("", response_model=BloodWorkPanelResponse, status_code=status.HTTP_201_CREATED)
async def create_blood_work_panel(
    data: BloodWorkPanelCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new blood work panel (manual entry)."""
    panel = BloodWorkPanel(
        user_id=user_id,
        lab_name=data.lab_name,
        test_date=data.test_date,
        report_image_url=data.report_image_url,
        source=data.source.value,
        ocr_confidence=data.ocr_confidence,
        # Vitamins & Minerals
        vitamin_d_ng_ml=data.vitamin_d_ng_ml,
        vitamin_b12_pg_ml=data.vitamin_b12_pg_ml,
        folate_ng_ml=data.folate_ng_ml,
        iron_mcg_dl=data.iron_mcg_dl,
        ferritin_ng_ml=data.ferritin_ng_ml,
        tibc_mcg_dl=data.tibc_mcg_dl,
        vitamin_a_mcg_dl=data.vitamin_a_mcg_dl,
        vitamin_e_mg_dl=data.vitamin_e_mg_dl,
        zinc_mcg_dl=data.zinc_mcg_dl,
        magnesium_mg_dl=data.magnesium_mg_dl,
        calcium_mg_dl=data.calcium_mg_dl,
        # Metabolic
        fasting_glucose_mg_dl=data.fasting_glucose_mg_dl,
        hba1c_percent=data.hba1c_percent,
        insulin_miu_ml=data.insulin_miu_ml,
        homa_ir=data.homa_ir,
        # Lipids
        total_cholesterol_mg_dl=data.total_cholesterol_mg_dl,
        ldl_mg_dl=data.ldl_mg_dl,
        hdl_mg_dl=data.hdl_mg_dl,
        triglycerides_mg_dl=data.triglycerides_mg_dl,
        vldl_mg_dl=data.vldl_mg_dl,
        # Hormones
        testosterone_total_ng_dl=data.testosterone_total_ng_dl,
        testosterone_free_pg_ml=data.testosterone_free_pg_ml,
        estradiol_pg_ml=data.estradiol_pg_ml,
        tsh_miu_l=data.tsh_miu_l,
        t3_ng_dl=data.t3_ng_dl,
        t4_mcg_dl=data.t4_mcg_dl,
        cortisol_mcg_dl=data.cortisol_mcg_dl,
        # CBC
        hemoglobin_g_dl=data.hemoglobin_g_dl,
        hematocrit_percent=data.hematocrit_percent,
        rbc_million_per_ul=data.rbc_million_per_ul,
        wbc_thousand_per_ul=data.wbc_thousand_per_ul,
        platelets_thousand_per_ul=data.platelets_thousand_per_ul,
        mcv_fl=data.mcv_fl,
        mch_pg=data.mch_pg,
        mchc_g_dl=data.mchc_g_dl,
        # Liver & Kidney
        alt_u_l=data.alt_u_l,
        ast_u_l=data.ast_u_l,
        alp_u_l=data.alp_u_l,
        bilirubin_mg_dl=data.bilirubin_mg_dl,
        creatinine_mg_dl=data.creatinine_mg_dl,
        bun_mg_dl=data.bun_mg_dl,
        egfr_ml_min=data.egfr_ml_min,
    )
    db.add(panel)
    await db.commit()
    await db.refresh(panel)
    return panel


@router.get("", response_model=list[BloodWorkPanelResponse])
async def list_blood_work_panels(
    limit: int = 10,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List user's blood work panels, ordered by test date (most recent first)."""
    result = await db.execute(
        select(BloodWorkPanel)
        .where(BloodWorkPanel.user_id == user_id)
        .order_by(BloodWorkPanel.test_date.desc())
        .limit(limit)
    )
    panels = result.scalars().all()
    return panels


@router.get("/latest/summary", response_model=BloodWorkSummary)
async def get_latest_summary(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get summary of latest blood work for dashboard."""
    # Get the most recent panel
    result = await db.execute(
        select(BloodWorkPanel)
        .where(BloodWorkPanel.user_id == user_id)
        .order_by(BloodWorkPanel.test_date.desc())
        .limit(1)
    )
    panel = result.scalar_one_or_none()

    if not panel:
        return BloodWorkSummary(has_data=False)

    # Count markers and classify them
    optimal_count = 0
    suboptimal_count = 0
    out_of_range_count = 0
    total_markers = 0
    critical_markers = []
    top_concerns = []

    for marker_key in REFERENCE_RANGES.keys():
        value = getattr(panel, marker_key, None)
        if value is not None:
            total_markers += 1
            marker_status = classify_marker_status(value, marker_key)
            ref = REFERENCE_RANGES[marker_key]

            if marker_status == MarkerStatus.OPTIMAL:
                optimal_count += 1
            elif marker_status in (MarkerStatus.SUBOPTIMAL_LOW, MarkerStatus.SUBOPTIMAL_HIGH):
                suboptimal_count += 1
            else:
                out_of_range_count += 1
                critical_markers.append(ref.name)
                if marker_status == MarkerStatus.LOW:
                    top_concerns.append(f"Low {ref.name}")
                else:
                    top_concerns.append(f"High {ref.name}")

    # Calculate days since test
    days_since = (datetime.utcnow().date() - panel.test_date.date()).days

    # Get health score from AI analysis if available
    health_score = None
    if panel.ai_analysis and "health_score" in panel.ai_analysis:
        health_score = panel.ai_analysis["health_score"]

    return BloodWorkSummary(
        has_data=True,
        latest_panel_id=panel.id,
        latest_test_date=panel.test_date,
        days_since_test=days_since,
        health_score=health_score,
        total_markers_tested=total_markers,
        optimal_count=optimal_count,
        suboptimal_count=suboptimal_count,
        out_of_range_count=out_of_range_count,
        critical_markers=critical_markers[:5],  # Top 5
        top_concerns=top_concerns[:5],
    )


@router.get("/trends/{marker_key}", response_model=BloodWorkTrendResponse)
async def get_marker_trend(
    marker_key: str,
    months: int = 12,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get historical trend for a specific marker."""
    if marker_key not in REFERENCE_RANGES:
        raise HTTPException(status_code=400, detail=f"Unknown marker: {marker_key}")

    ref = REFERENCE_RANGES[marker_key]
    start_date = datetime.utcnow() - timedelta(days=months * 30)

    # Get all panels with this marker
    result = await db.execute(
        select(BloodWorkPanel)
        .where(
            and_(
                BloodWorkPanel.user_id == user_id,
                BloodWorkPanel.test_date >= start_date,
            )
        )
        .order_by(BloodWorkPanel.test_date.asc())
    )
    panels = result.scalars().all()

    # Extract data points
    data_points = []
    values = []
    for panel in panels:
        value = getattr(panel, marker_key, None)
        if value is not None:
            values.append(value)
            data_points.append(
                TrendDataPoint(
                    test_date=panel.test_date,
                    value=value,
                    status=classify_marker_status(value, marker_key),
                )
            )

    # Calculate statistics
    latest_value = values[-1] if values else None
    previous_value = values[-2] if len(values) > 1 else None
    change_percent = None
    if latest_value and previous_value and previous_value != 0:
        change_percent = ((latest_value - previous_value) / previous_value) * 100

    # Determine trend direction
    trend_direction = None
    if len(values) >= 2:
        if latest_value > previous_value:
            trend_direction = "increasing"
        elif latest_value < previous_value:
            trend_direction = "decreasing"
        else:
            trend_direction = "stable"

    return BloodWorkTrendResponse(
        marker_key=marker_key,
        marker_name=ref.name,
        unit=ref.unit,
        reference_low=ref.low,
        reference_high=ref.high,
        optimal_low=ref.optimal_low,
        optimal_high=ref.optimal_high,
        data_points=data_points,
        trend_direction=trend_direction,
        latest_value=latest_value,
        previous_value=previous_value,
        change_percent=change_percent,
        min_value=min(values) if values else None,
        max_value=max(values) if values else None,
        avg_value=sum(values) / len(values) if values else None,
    )


@router.get("/{panel_id}", response_model=BloodWorkPanelResponse)
async def get_blood_work_panel(
    panel_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific blood work panel."""
    result = await db.execute(
        select(BloodWorkPanel).where(
            and_(BloodWorkPanel.id == panel_id, BloodWorkPanel.user_id == user_id)
        )
    )
    panel = result.scalar_one_or_none()
    if not panel:
        raise HTTPException(status_code=404, detail="Blood work panel not found")
    return panel


@router.patch("/{panel_id}", response_model=BloodWorkPanelResponse)
async def update_blood_work_panel(
    panel_id: str,
    data: BloodWorkPanelUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update a blood work panel."""
    result = await db.execute(
        select(BloodWorkPanel).where(
            and_(BloodWorkPanel.id == panel_id, BloodWorkPanel.user_id == user_id)
        )
    )
    panel = result.scalar_one_or_none()
    if not panel:
        raise HTTPException(status_code=404, detail="Blood work panel not found")

    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(panel, field, value)

    # Clear cached analysis if markers were updated
    marker_fields = set(REFERENCE_RANGES.keys())
    if marker_fields.intersection(update_data.keys()):
        panel.ai_analysis = None
        panel.ai_analyzed_at = None

    panel.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(panel)
    return panel


@router.delete("/{panel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blood_work_panel(
    panel_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a blood work panel."""
    result = await db.execute(
        select(BloodWorkPanel).where(
            and_(BloodWorkPanel.id == panel_id, BloodWorkPanel.user_id == user_id)
        )
    )
    panel = result.scalar_one_or_none()
    if not panel:
        raise HTTPException(status_code=404, detail="Blood work panel not found")

    await db.delete(panel)
    await db.commit()


# =============================================================================
# OCR Endpoints
# =============================================================================


@router.post("/ocr", response_model=BloodWorkOCRResponse)
async def extract_blood_work_ocr(
    data: BloodWorkOCRRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Extract blood work values from image using OCR."""
    # Import service here to avoid circular imports
    from app.services.blood_work_analyzer import get_blood_work_analyzer

    if not data.image_base64 and not data.image_url:
        raise HTTPException(
            status_code=400,
            detail="Either image_base64 or image_url must be provided"
        )

    analyzer = get_blood_work_analyzer()
    result = await analyzer.extract_from_image(
        image_base64=data.image_base64,
        image_url=data.image_url,
        mime_type=data.mime_type,
    )
    return result


@router.post("/confirm-ocr", response_model=BloodWorkPanelResponse, status_code=status.HTTP_201_CREATED)
async def confirm_ocr_extraction(
    data: BloodWorkConfirmOCRRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Save OCR-extracted values (with user corrections) as a new panel."""
    # Create panel with confirmed values
    panel_data = {
        "lab_name": data.lab_name,
        "test_date": data.test_date,
        "report_image_url": data.image_url,
        "source": "ocr",
        "ocr_confidence": data.ocr_confidence,
    }

    # Add all confirmed marker values
    for marker_key, value in data.markers.items():
        if marker_key in REFERENCE_RANGES and value is not None:
            panel_data[marker_key] = value

    panel = BloodWorkPanel(user_id=user_id, **panel_data)
    db.add(panel)
    await db.commit()
    await db.refresh(panel)
    return panel


# =============================================================================
# Analysis Endpoints
# =============================================================================


@router.post("/{panel_id}/analyze", response_model=BloodWorkAnalysisResponse)
async def analyze_blood_work_panel(
    panel_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Run AI analysis on a blood work panel."""
    # Import service here to avoid circular imports
    from app.services.blood_work_analyzer import get_blood_work_analyzer

    result = await db.execute(
        select(BloodWorkPanel).where(
            and_(BloodWorkPanel.id == panel_id, BloodWorkPanel.user_id == user_id)
        )
    )
    panel = result.scalar_one_or_none()
    if not panel:
        raise HTTPException(status_code=404, detail="Blood work panel not found")

    # Get user profile for context
    from app.infrastructure.database.models import UserProfile
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    user_profile = profile_result.scalar_one_or_none()

    # Get previous panels for trend context
    prev_result = await db.execute(
        select(BloodWorkPanel)
        .where(
            and_(
                BloodWorkPanel.user_id == user_id,
                BloodWorkPanel.test_date < panel.test_date,
            )
        )
        .order_by(BloodWorkPanel.test_date.desc())
        .limit(3)
    )
    previous_panels = prev_result.scalars().all()

    # Run analysis
    analyzer = get_blood_work_analyzer()
    analysis = await analyzer.analyze_panel(
        panel=panel,
        user_profile=user_profile,
        previous_panels=previous_panels,
    )

    # Cache the analysis
    panel.ai_analysis = analysis.model_dump()
    panel.ai_analyzed_at = datetime.utcnow()
    await db.commit()

    return analysis


@router.post("/{panel_id}/apply-recommendations", response_model=ApplyRecommendationsResponse)
async def apply_recommendations(
    panel_id: str,
    data: ApplyRecommendationsRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Apply recommendations from blood work analysis."""
    # Import service here to avoid circular imports
    from app.services.blood_work_integrations import get_blood_work_integration_service

    result = await db.execute(
        select(BloodWorkPanel).where(
            and_(BloodWorkPanel.id == panel_id, BloodWorkPanel.user_id == user_id)
        )
    )
    panel = result.scalar_one_or_none()
    if not panel:
        raise HTTPException(status_code=404, detail="Blood work panel not found")

    if not panel.ai_analysis:
        raise HTTPException(
            status_code=400,
            detail="Panel has no analysis. Run /analyze first."
        )

    integration_service = get_blood_work_integration_service(db)
    response = await integration_service.apply_recommendations(
        user_id=user_id,
        analysis=panel.ai_analysis,
        apply_supplements=data.apply_supplements,
        apply_targets=data.apply_targets,
    )
    return response
