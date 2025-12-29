"""Menstrual cycle tracking schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FlowIntensity(str, Enum):
    """Flow intensity levels."""
    spotting = "spotting"
    light = "light"
    medium = "medium"
    heavy = "heavy"


class CyclePhase(str, Enum):
    """Menstrual cycle phases."""
    menstruation = "menstruation"
    follicular = "follicular"
    ovulation = "ovulation"
    luteal = "luteal"


class Symptom(str, Enum):
    """Common menstrual symptoms."""
    cramps = "cramps"
    bloating = "bloating"
    headache = "headache"
    fatigue = "fatigue"
    breast_tenderness = "breast_tenderness"
    mood_swings = "mood_swings"
    back_pain = "back_pain"
    nausea = "nausea"
    acne = "acne"
    insomnia = "insomnia"
    cravings = "cravings"


# =============================================================================
# Request Schemas
# =============================================================================


class MenstrualLogCreate(BaseModel):
    """Request body for logging menstrual cycle data."""

    date: datetime
    is_period_day: bool = False
    flow_intensity: FlowIntensity | None = None
    symptoms: list[str] | None = Field(default_factory=list)
    mood: int | None = Field(None, ge=1, le=5)
    energy_level: int | None = Field(None, ge=1, le=5)
    notes: str | None = None


class MenstrualLogUpdate(BaseModel):
    """Request body for updating menstrual cycle log."""

    is_period_day: bool | None = None
    flow_intensity: FlowIntensity | None = None
    symptoms: list[str] | None = None
    mood: int | None = Field(None, ge=1, le=5)
    energy_level: int | None = Field(None, ge=1, le=5)
    notes: str | None = None


class CycleSettingsUpdate(BaseModel):
    """Request body for updating cycle settings."""

    average_cycle_length: int | None = Field(None, ge=21, le=45)
    average_period_length: int | None = Field(None, ge=2, le=10)
    last_period_start: datetime | None = None
    notify_period_reminder: bool | None = None
    reminder_days_before: int | None = Field(None, ge=1, le=7)


# =============================================================================
# Response Schemas
# =============================================================================


class MenstrualLogResponse(BaseModel):
    """Response body for menstrual cycle log."""

    id: str
    date: datetime
    is_period_day: bool
    flow_intensity: str | None
    symptoms: list[str] | None
    mood: int | None
    energy_level: int | None
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class CycleSettingsResponse(BaseModel):
    """Response body for cycle settings."""

    id: str
    average_cycle_length: int
    average_period_length: int
    last_period_start: datetime | None
    notify_period_reminder: bool
    reminder_days_before: int

    class Config:
        from_attributes = True


class CycleStatusResponse(BaseModel):
    """Response body for current cycle status."""

    current_phase: str  # menstruation, follicular, ovulation, luteal
    cycle_day: int
    days_until_period: int | None
    next_period_date: datetime | None
    is_fertile_window: bool
    phase_day: int  # Day within the current phase
    phase_days_remaining: int  # Days remaining in current phase


class CycleRecommendationsResponse(BaseModel):
    """Response body for phase-based recommendations."""

    phase: str
    phase_description: str
    nutrition_tips: list[str]
    recommended_foods: list[str]
    foods_to_limit: list[str]
    workout_tips: list[str]
    workout_intensity: str  # light, moderate, high
    self_care_tips: list[str]


class CalendarDayResponse(BaseModel):
    """Response body for a single calendar day."""

    date: datetime
    is_period_day: bool
    is_predicted_period: bool
    is_fertile_window: bool
    is_ovulation_day: bool
    phase: str | None
    has_log: bool
    flow_intensity: str | None = None
    symptoms: list[str] | None = None
    mood: int | None = None
    energy_level: int | None = None


class CycleHistoryResponse(BaseModel):
    """Response body for cycle history summary."""

    logs: list[MenstrualLogResponse]
    average_cycle_length: int
    average_period_length: int
    last_period_start: datetime | None
    total_periods_logged: int
