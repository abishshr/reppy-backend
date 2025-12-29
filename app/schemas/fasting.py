"""Pydantic schemas for intermittent fasting."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FastingProtocol(str, Enum):
    """Supported fasting protocols."""

    IF_16_8 = "16:8"
    IF_18_6 = "18:6"
    IF_20_4 = "20:4"
    OMAD = "omad"
    EXTENDED_24H = "24h"
    EXTENDED_36H = "36h"
    EXTENDED_48H = "48h"
    FIVE_TWO = "5:2"
    CUSTOM = "custom"


class FastingStatus(str, Enum):
    """Fasting session status."""

    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Protocol durations in hours
PROTOCOL_DURATIONS = {
    FastingProtocol.IF_16_8: 16,
    FastingProtocol.IF_18_6: 18,
    FastingProtocol.IF_20_4: 20,
    FastingProtocol.OMAD: 23,
    FastingProtocol.EXTENDED_24H: 24,
    FastingProtocol.EXTENDED_36H: 36,
    FastingProtocol.EXTENDED_48H: 48,
    FastingProtocol.FIVE_TWO: 16,  # Default for 5:2 (restricted calorie days)
}


# =============================================================================
# Request Schemas
# =============================================================================


class FastingSessionCreate(BaseModel):
    """Request body for starting a fast."""

    protocol: FastingProtocol
    duration_hours: Optional[float] = Field(
        None,
        ge=1,
        le=168,  # Max 1 week
        description="Custom duration in hours. Required for custom protocol.",
    )
    notes: Optional[str] = None


class FastingSessionStop(BaseModel):
    """Request body for ending a fast."""

    completed: bool = Field(
        True, description="True if fast was completed successfully, False if cancelled."
    )
    notes: Optional[str] = None


class FastingSettingsUpdate(BaseModel):
    """Request body for updating fasting settings."""

    preferred_protocol: Optional[str] = None
    eating_window_start: Optional[str] = Field(
        None, pattern=r"^\d{2}:\d{2}$", description="HH:MM format"
    )
    eating_window_end: Optional[str] = Field(
        None, pattern=r"^\d{2}:\d{2}$", description="HH:MM format"
    )
    notify_fast_complete: Optional[bool] = None
    notify_reminder_before_min: Optional[int] = Field(None, ge=0, le=120)
    fasting_days_of_week: Optional[list[int]] = Field(
        None, description="Days of week for 5:2 diet (1=Mon, 7=Sun)"
    )
    fasting_calorie_limit: Optional[int] = Field(
        None, ge=0, le=1000, description="Calorie limit on fasting days"
    )


# =============================================================================
# Response Schemas
# =============================================================================


class FastingSessionResponse(BaseModel):
    """Response for a fasting session."""

    id: str
    user_id: str
    protocol: str
    started_at: datetime
    target_end_at: datetime
    actual_end_at: Optional[datetime] = None
    status: str
    duration_hours: float
    notes: Optional[str] = None
    created_at: datetime

    # Computed fields (added dynamically)
    elapsed_seconds: int = 0
    remaining_seconds: int = 0
    progress_percentage: float = 0.0

    class Config:
        from_attributes = True


class FastingStatsResponse(BaseModel):
    """Statistics about user's fasting history."""

    current_fasting_streak: int
    longest_fasting_streak: int
    total_fasts_completed: int
    total_hours_fasted: float
    average_fast_duration_hours: float
    most_used_protocol: Optional[str] = None
    this_week_fasts: int
    this_month_fasts: int
    fasts_by_protocol: dict[str, int] = {}


class FastingSettingsResponse(BaseModel):
    """Response for fasting settings."""

    id: str
    user_id: str
    preferred_protocol: Optional[str] = None
    eating_window_start: Optional[str] = None
    eating_window_end: Optional[str] = None
    notify_fast_complete: bool
    notify_reminder_before_min: int
    fasting_days_of_week: Optional[list[int]] = None
    fasting_calorie_limit: Optional[int] = None
    current_fasting_streak: int
    longest_fasting_streak: int
    last_fast_completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ActiveFastResponse(BaseModel):
    """Response for checking active fast status."""

    is_fasting: bool
    session: Optional[FastingSessionResponse] = None
    eating_window_active: bool = False
    next_eating_window_starts: Optional[datetime] = None
    next_eating_window_ends: Optional[datetime] = None


class FastingProtocolInfo(BaseModel):
    """Information about a fasting protocol."""

    protocol: str
    name: str
    description: str
    fasting_hours: int
    eating_hours: int
    difficulty: str  # easy, moderate, advanced, expert
    recommended_for: list[str]


class FastingHistoryResponse(BaseModel):
    """Paginated fasting history response."""

    items: list[FastingSessionResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
