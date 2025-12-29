"""Circadian rhythm and meal timing schemas."""

from datetime import time

from pydantic import BaseModel, Field


class MealTimingAnalysisResponse(BaseModel):
    """Analysis of user's meal timing patterns."""

    average_first_meal: str | None = None  # HH:MM format
    average_last_meal: str | None = None  # HH:MM format
    eating_window_hours: float | None = None
    late_night_eating_frequency: float = Field(
        ..., ge=0, le=100, description="Percentage of days with late eating"
    )
    consistency_score: int = Field(..., ge=0, le=100)
    meal_time_variance_minutes: float = Field(..., ge=0)


class CircadianRecommendation(BaseModel):
    """A circadian-based meal timing recommendation."""

    priority: str  # "high", "medium", "low"
    title: str
    description: str
    action: str
    benefit: str


class CircadianAnalysisResponse(BaseModel):
    """Complete circadian analysis with recommendations."""

    analysis: MealTimingAnalysisResponse
    recommendations: list[CircadianRecommendation] = Field(default_factory=list)
    has_data: bool = True


class OptimalMealTimesRequest(BaseModel):
    """Request for personalized optimal meal times."""

    wake_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM format")
    sleep_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM format")


class OptimalMealTimesResponse(BaseModel):
    """Personalized optimal meal times based on sleep schedule."""

    breakfast: str  # HH:MM format
    lunch: str  # HH:MM format
    dinner: str  # HH:MM format
    eating_cutoff: str  # HH:MM format
    eating_window_hours: int = 10
