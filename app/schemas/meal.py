"""Meal logging schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class MealItem(BaseModel):
    """Individual food item in a meal."""

    name: str = Field(..., min_length=1)
    quantity: float | None = Field(None, gt=0)
    unit: str | None = None  # grams, oz, cup, piece, etc.
    testosterone_impact: str | None = None  # "boosts", "reduces", "neutral"


class MealSuggestion(BaseModel):
    """AI-suggested meal log before confirmation."""

    items: list[MealItem]
    estimated_calories: int = Field(..., ge=0)
    estimated_protein_g: float = Field(..., ge=0)
    estimated_carbs_g: float = Field(..., ge=0)
    estimated_fat_g: float = Field(..., ge=0)
    estimated_sugar_g: float | None = Field(None, ge=0)
    estimated_fiber_g: float | None = Field(None, ge=0)
    estimated_sodium_mg: float | None = Field(None, ge=0)
    estimated_saturated_fat_g: float | None = Field(None, ge=0)
    estimated_cholesterol_mg: float | None = Field(None, ge=0)
    confidence: float = Field(..., ge=0, le=1)
    notes: str | None = None  # Educational tips
    clarifying_questions: list[str] = Field(default_factory=list)
    suggestion_id: str | None = None  # For tracking pending suggestions


class MealLogCreate(BaseModel):
    """Request body for logging a confirmed meal."""

    items: list[MealItem]
    meal_type: str | None = Field(
        None,
        pattern="^(breakfast|lunch|dinner|snack)$",
    )
    calories: int = Field(..., ge=0)
    protein_g: float = Field(..., ge=0)
    carbs_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)
    sugar_g_est: float | None = Field(None, ge=0)
    fiber_g_est: float | None = Field(None, ge=0)
    sodium_mg_est: float | None = Field(None, ge=0)
    saturated_fat_g_est: float | None = Field(None, ge=0)
    cholesterol_mg_est: float | None = Field(None, ge=0)
    confidence: float = Field(..., ge=0, le=1)
    notes: str | None = None
    image_url: str | None = None
    logged_at: datetime | None = None


class MealLogResponse(BaseModel):
    """Response body for a logged meal."""

    id: str
    user_id: str
    logged_at: datetime
    meal_type: str | None
    items: list[MealItem]
    calories: int | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    sugar_g_est: float | None
    fiber_g_est: float | None
    sodium_mg_est: float | None
    saturated_fat_g_est: float | None
    cholesterol_mg_est: float | None
    confidence: float | None
    notes: str | None
    image_url: str | None
    created_at: datetime

    # Testosterone impact analysis (for male users)
    testosterone_impact: str | None = None  # "boosting", "reducing", "mixed", "neutral"

    class Config:
        from_attributes = True


class TestosteroneSummaryResponse(BaseModel):
    """Response for daily testosterone impact summary."""

    boosting_count: int = 0
    reducing_count: int = 0
    neutral_count: int = 0
    overall_rating: str = "neutral"  # "great", "good", "neutral", "poor"


# Health Impact Score Schemas
class HealthScoreBreakdown(BaseModel):
    """Breakdown of health score components."""

    nutritional_balance: int = Field(..., ge=0, le=100)
    processing_level: int = Field(..., ge=0, le=100)
    ingredient_quality: int = Field(..., ge=0, le=100)
    macro_balance: int = Field(..., ge=0, le=100)


class MealHealthAnalysisResponse(BaseModel):
    """AI-powered health analysis of a meal."""

    overall_score: int = Field(..., ge=0, le=100)
    breakdown: HealthScoreBreakdown
    insights: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    positive_aspects: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class DailyHealthSummary(BaseModel):
    """Daily health summary across all meals."""

    average_score: float = Field(..., ge=0, le=100)
    meal_count: int
    overall_rating: str  # "excellent", "good", "fair", "needs_improvement", "unknown"
    analyzed_at: datetime


# Nutrient Synergy Schemas
class SynergyInsight(BaseModel):
    """A nutrient synergy or interaction insight."""

    type: str  # "beneficial" or "inhibiting"
    title: str
    description: str
    foods_involved: list[str]
    impact: str  # "high", "medium", "low"


class MealSynergyResponse(BaseModel):
    """Nutrient synergy analysis for a meal."""

    insights: list[SynergyInsight] = Field(default_factory=list)
    beneficial_count: int = 0
    inhibiting_count: int = 0
