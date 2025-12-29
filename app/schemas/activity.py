"""Activity tracking schemas."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class StepsSyncRequest(BaseModel):
    """Request body for syncing steps from Apple Health."""

    date: date
    steps: int = Field(..., ge=0)
    source: str = Field(default="apple_health")


class ActivityResponse(BaseModel):
    """Response body for a single day's activity."""

    id: str
    user_id: str
    date: datetime
    steps: int
    source: str | None
    synced_at: datetime

    class Config:
        from_attributes = True


class ActivitySummary(BaseModel):
    """Summary of activity over a period."""

    today_steps: int = 0
    today_goal: int = 10000
    today_progress_percent: float = 0.0
    seven_day_average: float = 0.0
    seven_day_total: int = 0
    streak_days: int = 0  # Days in a row meeting goal
    daily_data: list[ActivityResponse] = Field(default_factory=list)
