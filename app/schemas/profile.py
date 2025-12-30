"""User profile schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProfileCreate(BaseModel):
    """Request body for creating a user profile."""

    name: str = Field(..., min_length=1, max_length=100)
    age: int | None = Field(None, ge=13, le=120)
    sex: str | None = Field(None, pattern="^(male|female|other)$")
    height_cm: float | None = Field(None, ge=50, le=300)
    weight_kg: float | None = Field(None, ge=20, le=500)
    activity_level: str | None = Field(
        None,
        pattern="^(sedentary|light|moderate|active|very_active)$",
    )
    goals: list[str] | None = Field(default_factory=list)
    diet_style: str | None = Field(None)
    allergies: list[str] | None = Field(default_factory=list)
    injuries: list[str] | None = Field(default_factory=list)
    medical_conditions: list[str] | None = Field(default_factory=list)
    preferred_ingredients: list[str] | None = Field(default_factory=list)
    equipment: list[str] | None = Field(default_factory=list)
    timezone: str | None = Field(default="UTC")
    daily_steps_goal: int | None = Field(default=10000, ge=0, le=100000)


class ProfileUpdate(BaseModel):
    """Request body for updating a user profile."""

    name: str | None = Field(None, min_length=1, max_length=100)
    age: int | None = Field(None, ge=13, le=120)
    sex: str | None = Field(None, pattern="^(male|female|other)$")
    height_cm: float | None = Field(None, ge=50, le=300)
    weight_kg: float | None = Field(None, ge=20, le=500)
    activity_level: str | None = None
    goals: list[str] | None = None
    diet_style: str | None = None
    allergies: list[str] | None = None
    injuries: list[str] | None = None
    medical_conditions: list[str] | None = None
    preferred_ingredients: list[str] | None = None
    equipment: list[str] | None = None
    timezone: str | None = None
    daily_calorie_target: int | None = Field(None, ge=500, le=10000)
    daily_protein_target: float | None = Field(None, ge=0, le=500)
    daily_carbs_target: float | None = Field(None, ge=0, le=1000)
    daily_fat_target: float | None = Field(None, ge=0, le=500)
    # Micronutrient targets
    daily_sugar_target_g: float | None = Field(None, ge=0, le=200)
    daily_fiber_target_g: float | None = Field(None, ge=0, le=100)
    daily_sodium_target_mg: float | None = Field(None, ge=0, le=10000)
    daily_saturated_fat_target_g: float | None = Field(None, ge=0, le=100)
    daily_steps_goal: int | None = Field(None, ge=0, le=100000)
    onboarding_completed: bool | None = None


class ProfileResponse(BaseModel):
    """Response body for user profile."""

    id: str
    user_id: str
    name: str | None
    age: int | None
    sex: str | None
    height_cm: float | None
    weight_kg: float | None
    activity_level: str | None
    goals: list[str] = Field(default_factory=list)
    diet_style: str | None
    allergies: list[str] = Field(default_factory=list)
    injuries: list[str] = Field(default_factory=list)
    medical_conditions: list[str] = Field(default_factory=list)
    preferred_ingredients: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    timezone: str | None

    daily_calorie_target: int | None
    daily_protein_target: float | None
    daily_carbs_target: float | None
    daily_fat_target: float | None
    # Micronutrient targets
    daily_sugar_target_g: float | None
    daily_fiber_target_g: float | None
    daily_sodium_target_mg: float | None
    daily_saturated_fat_target_g: float | None
    daily_steps_goal: int | None
    daily_water_goal_ml: int | None
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime

    @field_validator('goals', 'allergies', 'injuries', 'medical_conditions', 'preferred_ingredients', 'equipment', mode='before')
    @classmethod
    def convert_none_to_list(cls, v: Any) -> list[str]:
        """Convert None values to empty lists."""
        if v is None:
            return []
        return v

    class Config:
        from_attributes = True
