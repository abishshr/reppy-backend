"""Blood work tracking schemas with reference ranges."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# =============================================================================
# Reference Ranges
# =============================================================================

class MarkerReference(BaseModel):
    """Reference range for a blood marker."""

    name: str
    unit: str
    low: float
    high: float
    optimal_low: float | None = None
    optimal_high: float | None = None


# Standard reference ranges for adults
REFERENCE_RANGES: dict[str, MarkerReference] = {
    # Vitamins & Minerals
    "vitamin_d_ng_ml": MarkerReference(name="Vitamin D", unit="ng/mL", low=30, high=100, optimal_low=40, optimal_high=60),
    "vitamin_b12_pg_ml": MarkerReference(name="Vitamin B12", unit="pg/mL", low=200, high=900, optimal_low=400, optimal_high=800),
    "folate_ng_ml": MarkerReference(name="Folate", unit="ng/mL", low=3, high=17, optimal_low=5, optimal_high=15),
    "iron_mcg_dl": MarkerReference(name="Iron", unit="mcg/dL", low=60, high=170, optimal_low=80, optimal_high=150),
    "ferritin_ng_ml": MarkerReference(name="Ferritin", unit="ng/mL", low=12, high=300, optimal_low=50, optimal_high=150),
    "tibc_mcg_dl": MarkerReference(name="TIBC", unit="mcg/dL", low=250, high=370, optimal_low=260, optimal_high=350),
    "vitamin_a_mcg_dl": MarkerReference(name="Vitamin A", unit="mcg/dL", low=30, high=80, optimal_low=40, optimal_high=70),
    "vitamin_e_mg_dl": MarkerReference(name="Vitamin E", unit="mg/dL", low=5.5, high=17, optimal_low=8, optimal_high=15),
    "zinc_mcg_dl": MarkerReference(name="Zinc", unit="mcg/dL", low=60, high=130, optimal_low=80, optimal_high=120),
    "magnesium_mg_dl": MarkerReference(name="Magnesium", unit="mg/dL", low=1.7, high=2.3, optimal_low=2.0, optimal_high=2.3),
    "calcium_mg_dl": MarkerReference(name="Calcium", unit="mg/dL", low=8.5, high=10.5, optimal_low=9.0, optimal_high=10.0),

    # Metabolic Panel
    "fasting_glucose_mg_dl": MarkerReference(name="Fasting Glucose", unit="mg/dL", low=70, high=99, optimal_low=75, optimal_high=90),
    "hba1c_percent": MarkerReference(name="HbA1c", unit="%", low=4.0, high=5.6, optimal_low=4.5, optimal_high=5.3),
    "insulin_miu_ml": MarkerReference(name="Insulin", unit="mIU/mL", low=2.6, high=24.9, optimal_low=3, optimal_high=10),
    "homa_ir": MarkerReference(name="HOMA-IR", unit="", low=0, high=2.5, optimal_low=0, optimal_high=1.5),

    # Lipid Panel
    "total_cholesterol_mg_dl": MarkerReference(name="Total Cholesterol", unit="mg/dL", low=125, high=200, optimal_low=150, optimal_high=180),
    "ldl_mg_dl": MarkerReference(name="LDL", unit="mg/dL", low=0, high=100, optimal_low=0, optimal_high=70),
    "hdl_mg_dl": MarkerReference(name="HDL", unit="mg/dL", low=40, high=100, optimal_low=50, optimal_high=90),
    "triglycerides_mg_dl": MarkerReference(name="Triglycerides", unit="mg/dL", low=0, high=150, optimal_low=0, optimal_high=100),
    "vldl_mg_dl": MarkerReference(name="VLDL", unit="mg/dL", low=5, high=40, optimal_low=5, optimal_high=25),

    # Hormones
    "testosterone_total_ng_dl": MarkerReference(name="Testosterone (Total)", unit="ng/dL", low=300, high=1000, optimal_low=500, optimal_high=900),
    "testosterone_free_pg_ml": MarkerReference(name="Testosterone (Free)", unit="pg/mL", low=5, high=21, optimal_low=10, optimal_high=20),
    "estradiol_pg_ml": MarkerReference(name="Estradiol", unit="pg/mL", low=10, high=40, optimal_low=15, optimal_high=30),
    "tsh_miu_l": MarkerReference(name="TSH", unit="mIU/L", low=0.4, high=4.0, optimal_low=1.0, optimal_high=2.5),
    "t3_ng_dl": MarkerReference(name="T3", unit="ng/dL", low=80, high=200, optimal_low=100, optimal_high=180),
    "t4_mcg_dl": MarkerReference(name="T4", unit="mcg/dL", low=4.5, high=12.5, optimal_low=6, optimal_high=10),
    "cortisol_mcg_dl": MarkerReference(name="Cortisol", unit="mcg/dL", low=6, high=23, optimal_low=8, optimal_high=18),

    # CBC
    "hemoglobin_g_dl": MarkerReference(name="Hemoglobin", unit="g/dL", low=12.0, high=17.5, optimal_low=13, optimal_high=16),
    "hematocrit_percent": MarkerReference(name="Hematocrit", unit="%", low=36, high=50, optimal_low=38, optimal_high=48),
    "rbc_million_per_ul": MarkerReference(name="RBC", unit="M/uL", low=4.0, high=5.5, optimal_low=4.2, optimal_high=5.2),
    "wbc_thousand_per_ul": MarkerReference(name="WBC", unit="K/uL", low=4.5, high=11.0, optimal_low=5, optimal_high=9),
    "platelets_thousand_per_ul": MarkerReference(name="Platelets", unit="K/uL", low=150, high=400, optimal_low=175, optimal_high=350),
    "mcv_fl": MarkerReference(name="MCV", unit="fL", low=80, high=100, optimal_low=82, optimal_high=98),
    "mch_pg": MarkerReference(name="MCH", unit="pg", low=27, high=33, optimal_low=28, optimal_high=32),
    "mchc_g_dl": MarkerReference(name="MCHC", unit="g/dL", low=32, high=36, optimal_low=33, optimal_high=35),

    # Liver & Kidney
    "alt_u_l": MarkerReference(name="ALT", unit="U/L", low=7, high=56, optimal_low=10, optimal_high=35),
    "ast_u_l": MarkerReference(name="AST", unit="U/L", low=10, high=40, optimal_low=12, optimal_high=30),
    "alp_u_l": MarkerReference(name="ALP", unit="U/L", low=44, high=147, optimal_low=50, optimal_high=120),
    "bilirubin_mg_dl": MarkerReference(name="Bilirubin", unit="mg/dL", low=0.1, high=1.2, optimal_low=0.2, optimal_high=1.0),
    "creatinine_mg_dl": MarkerReference(name="Creatinine", unit="mg/dL", low=0.7, high=1.3, optimal_low=0.8, optimal_high=1.2),
    "bun_mg_dl": MarkerReference(name="BUN", unit="mg/dL", low=7, high=20, optimal_low=10, optimal_high=18),
    "egfr_ml_min": MarkerReference(name="eGFR", unit="mL/min", low=90, high=120, optimal_low=90, optimal_high=120),
}


# =============================================================================
# Enums
# =============================================================================

class MarkerStatus(str, Enum):
    """Status classification for a blood marker result."""

    LOW = "low"
    SUBOPTIMAL_LOW = "suboptimal_low"
    OPTIMAL = "optimal"
    SUBOPTIMAL_HIGH = "suboptimal_high"
    HIGH = "high"


class BloodWorkSource(str, Enum):
    """Source of blood work data entry."""

    MANUAL = "manual"
    OCR = "ocr"
    PDF_OCR = "pdf_ocr"


# =============================================================================
# Marker Result Schema
# =============================================================================

class BloodMarkerResult(BaseModel):
    """Result for a single blood marker with status classification."""

    marker_key: str
    name: str
    value: float
    unit: str
    status: MarkerStatus
    reference_low: float
    reference_high: float
    optimal_low: float | None = None
    optimal_high: float | None = None

    @property
    def color(self) -> str:
        """Return color for UI based on status."""
        colors = {
            MarkerStatus.LOW: "red",
            MarkerStatus.SUBOPTIMAL_LOW: "orange",
            MarkerStatus.OPTIMAL: "green",
            MarkerStatus.SUBOPTIMAL_HIGH: "orange",
            MarkerStatus.HIGH: "red",
        }
        return colors[self.status]


# =============================================================================
# Create/Update Schemas
# =============================================================================

class BloodWorkPanelCreate(BaseModel):
    """Request body for creating a blood work panel."""

    # Metadata
    lab_name: str | None = Field(None, max_length=200)
    test_date: datetime
    report_image_url: str | None = Field(None, max_length=500)
    source: BloodWorkSource = BloodWorkSource.MANUAL
    ocr_confidence: float | None = Field(None, ge=0, le=1)

    # Vitamins & Minerals
    vitamin_d_ng_ml: float | None = Field(None, ge=0)
    vitamin_b12_pg_ml: float | None = Field(None, ge=0)
    folate_ng_ml: float | None = Field(None, ge=0)
    iron_mcg_dl: float | None = Field(None, ge=0)
    ferritin_ng_ml: float | None = Field(None, ge=0)
    tibc_mcg_dl: float | None = Field(None, ge=0)
    vitamin_a_mcg_dl: float | None = Field(None, ge=0)
    vitamin_e_mg_dl: float | None = Field(None, ge=0)
    zinc_mcg_dl: float | None = Field(None, ge=0)
    magnesium_mg_dl: float | None = Field(None, ge=0)
    calcium_mg_dl: float | None = Field(None, ge=0)

    # Metabolic
    fasting_glucose_mg_dl: float | None = Field(None, ge=0)
    hba1c_percent: float | None = Field(None, ge=0)
    insulin_miu_ml: float | None = Field(None, ge=0)
    homa_ir: float | None = Field(None, ge=0)

    # Lipids
    total_cholesterol_mg_dl: float | None = Field(None, ge=0)
    ldl_mg_dl: float | None = Field(None, ge=0)
    hdl_mg_dl: float | None = Field(None, ge=0)
    triglycerides_mg_dl: float | None = Field(None, ge=0)
    vldl_mg_dl: float | None = Field(None, ge=0)

    # Hormones
    testosterone_total_ng_dl: float | None = Field(None, ge=0)
    testosterone_free_pg_ml: float | None = Field(None, ge=0)
    estradiol_pg_ml: float | None = Field(None, ge=0)
    tsh_miu_l: float | None = Field(None, ge=0)
    t3_ng_dl: float | None = Field(None, ge=0)
    t4_mcg_dl: float | None = Field(None, ge=0)
    cortisol_mcg_dl: float | None = Field(None, ge=0)

    # CBC
    hemoglobin_g_dl: float | None = Field(None, ge=0)
    hematocrit_percent: float | None = Field(None, ge=0)
    rbc_million_per_ul: float | None = Field(None, ge=0)
    wbc_thousand_per_ul: float | None = Field(None, ge=0)
    platelets_thousand_per_ul: float | None = Field(None, ge=0)
    mcv_fl: float | None = Field(None, ge=0)
    mch_pg: float | None = Field(None, ge=0)
    mchc_g_dl: float | None = Field(None, ge=0)

    # Liver & Kidney
    alt_u_l: float | None = Field(None, ge=0)
    ast_u_l: float | None = Field(None, ge=0)
    alp_u_l: float | None = Field(None, ge=0)
    bilirubin_mg_dl: float | None = Field(None, ge=0)
    creatinine_mg_dl: float | None = Field(None, ge=0)
    bun_mg_dl: float | None = Field(None, ge=0)
    egfr_ml_min: float | None = Field(None, ge=0)


class BloodWorkPanelUpdate(BaseModel):
    """Request body for updating a blood work panel (all fields optional)."""

    lab_name: str | None = None
    test_date: datetime | None = None

    # All 42 markers optional for partial updates
    vitamin_d_ng_ml: float | None = None
    vitamin_b12_pg_ml: float | None = None
    folate_ng_ml: float | None = None
    iron_mcg_dl: float | None = None
    ferritin_ng_ml: float | None = None
    tibc_mcg_dl: float | None = None
    vitamin_a_mcg_dl: float | None = None
    vitamin_e_mg_dl: float | None = None
    zinc_mcg_dl: float | None = None
    magnesium_mg_dl: float | None = None
    calcium_mg_dl: float | None = None
    fasting_glucose_mg_dl: float | None = None
    hba1c_percent: float | None = None
    insulin_miu_ml: float | None = None
    homa_ir: float | None = None
    total_cholesterol_mg_dl: float | None = None
    ldl_mg_dl: float | None = None
    hdl_mg_dl: float | None = None
    triglycerides_mg_dl: float | None = None
    vldl_mg_dl: float | None = None
    testosterone_total_ng_dl: float | None = None
    testosterone_free_pg_ml: float | None = None
    estradiol_pg_ml: float | None = None
    tsh_miu_l: float | None = None
    t3_ng_dl: float | None = None
    t4_mcg_dl: float | None = None
    cortisol_mcg_dl: float | None = None
    hemoglobin_g_dl: float | None = None
    hematocrit_percent: float | None = None
    rbc_million_per_ul: float | None = None
    wbc_thousand_per_ul: float | None = None
    platelets_thousand_per_ul: float | None = None
    mcv_fl: float | None = None
    mch_pg: float | None = None
    mchc_g_dl: float | None = None
    alt_u_l: float | None = None
    ast_u_l: float | None = None
    alp_u_l: float | None = None
    bilirubin_mg_dl: float | None = None
    creatinine_mg_dl: float | None = None
    bun_mg_dl: float | None = None
    egfr_ml_min: float | None = None


# =============================================================================
# Response Schemas
# =============================================================================

class BloodWorkPanelResponse(BloodWorkPanelCreate):
    """Full blood work panel response."""

    id: str
    user_id: str
    ai_analysis: dict | None = None
    ai_analyzed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# OCR Schemas
# =============================================================================

class BloodWorkOCRRequest(BaseModel):
    """Request for OCR extraction from image."""

    image_base64: str | None = None
    image_url: str | None = None
    mime_type: str = "image/jpeg"


class BloodWorkOCRResponse(BaseModel):
    """Response from OCR extraction."""

    success: bool
    confidence: float = Field(ge=0, le=1)
    lab_name: str | None = None
    test_date: datetime | None = None
    warnings: list[str] = []

    # Extracted marker values
    extracted_values: dict[str, float] = {}

    # Values that need manual review
    uncertain_values: dict[str, dict] = {}  # {marker_key: {value, confidence, raw_text}}


class BloodWorkConfirmOCRRequest(BaseModel):
    """Request to confirm/save OCR extracted values (with user corrections)."""

    lab_name: str | None = None
    test_date: datetime
    image_url: str | None = None
    ocr_confidence: float | None = None

    # User-confirmed marker values (may include corrections)
    markers: dict[str, float | None] = {}


# =============================================================================
# Analysis Schemas
# =============================================================================

class MarkerCategorySummary(BaseModel):
    """Summary for a category of markers."""

    category: str
    total_markers: int
    optimal_count: int
    suboptimal_count: int
    out_of_range_count: int
    markers: list[BloodMarkerResult]


class SupplementRecommendation(BaseModel):
    """Supplement recommendation based on blood work."""

    supplement_name: str
    reason: str
    dosage_suggestion: str | None = None
    priority: str = "medium"  # high, medium, low
    related_markers: list[str] = []


class NutritionRecommendation(BaseModel):
    """Nutrition recommendation based on blood work."""

    recommendation: str
    foods_to_increase: list[str] = []
    foods_to_limit: list[str] = []
    reason: str
    related_markers: list[str] = []


class WorkoutRecommendation(BaseModel):
    """Workout intensity/recovery recommendation based on blood work."""

    recommendation: str
    intensity_modifier: float = 1.0  # 0.7-1.0
    reason: str
    related_markers: list[str] = []


class LifestyleRecommendation(BaseModel):
    """General lifestyle recommendation based on blood work."""

    category: str  # sleep, stress, hydration, etc.
    recommendation: str
    reason: str


class TargetAdjustment(BaseModel):
    """Suggested micronutrient target adjustment."""

    nutrient: str
    current_target: float | None
    suggested_target: float
    unit: str
    reason: str


class BloodWorkAnalysisResponse(BaseModel):
    """Full AI analysis of blood work panel."""

    health_score: int = Field(ge=0, le=100)
    health_score_breakdown: dict[str, int] = {}  # {category: score}

    summary: str  # 2-3 sentence overall summary

    # Categorized markers
    categories: list[MarkerCategorySummary] = []

    # Critical flags
    critical_markers: list[BloodMarkerResult] = []

    # AI recommendations
    supplement_recommendations: list[SupplementRecommendation] = []
    nutrition_recommendations: list[NutritionRecommendation] = []
    workout_recommendations: list[WorkoutRecommendation] = []
    lifestyle_recommendations: list[LifestyleRecommendation] = []
    target_adjustments: list[TargetAdjustment] = []

    analyzed_at: datetime


class ApplyRecommendationsRequest(BaseModel):
    """Request to apply recommendations from analysis."""

    apply_supplements: bool = False  # Create suggested supplements
    apply_targets: bool = False  # Adjust micronutrient targets


class ApplyRecommendationsResponse(BaseModel):
    """Response after applying recommendations."""

    applied_actions: list[str] = []
    supplements_created: list[str] = []
    targets_updated: list[str] = []


# =============================================================================
# Trend Schemas
# =============================================================================

class TrendDataPoint(BaseModel):
    """Single data point in a marker trend."""

    test_date: datetime
    value: float
    status: MarkerStatus


class BloodWorkTrendResponse(BaseModel):
    """Historical trend for a specific marker."""

    marker_key: str
    marker_name: str
    unit: str
    reference_low: float
    reference_high: float
    optimal_low: float | None
    optimal_high: float | None

    data_points: list[TrendDataPoint] = []
    trend_direction: str | None = None  # improving, stable, declining

    # Statistics
    latest_value: float | None = None
    previous_value: float | None = None
    change_percent: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    avg_value: float | None = None


# =============================================================================
# Dashboard Summary
# =============================================================================

class BloodWorkSummary(BaseModel):
    """Summary of latest blood work for dashboard."""

    has_data: bool = False
    latest_panel_id: str | None = None
    latest_test_date: datetime | None = None
    days_since_test: int | None = None

    # Health score from latest panel
    health_score: int | None = None

    # Counts
    total_markers_tested: int = 0
    optimal_count: int = 0
    suboptimal_count: int = 0
    out_of_range_count: int = 0

    # Key concerns (if any)
    critical_markers: list[str] = []  # Marker names that need attention

    # Quick stats
    top_concerns: list[str] = []  # e.g., "Low Vitamin D", "High LDL"
