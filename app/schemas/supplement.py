"""Supplement tracking schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class SupplementNutrients(BaseModel):
    """Nutrient content per serving of a supplement."""

    # Vitamins
    vitamin_a_mcg: float | None = Field(None, ge=0)
    vitamin_c_mg: float | None = Field(None, ge=0)
    vitamin_d_mcg: float | None = Field(None, ge=0)
    vitamin_e_mg: float | None = Field(None, ge=0)
    vitamin_k_mcg: float | None = Field(None, ge=0)
    vitamin_b1_mg: float | None = Field(None, ge=0)  # Thiamin
    vitamin_b2_mg: float | None = Field(None, ge=0)  # Riboflavin
    vitamin_b3_mg: float | None = Field(None, ge=0)  # Niacin
    vitamin_b6_mg: float | None = Field(None, ge=0)
    vitamin_b9_mcg: float | None = Field(None, ge=0)  # Folate
    vitamin_b12_mcg: float | None = Field(None, ge=0)

    # Minerals
    calcium_mg: float | None = Field(None, ge=0)
    iron_mg: float | None = Field(None, ge=0)
    magnesium_mg: float | None = Field(None, ge=0)
    phosphorus_mg: float | None = Field(None, ge=0)
    potassium_mg: float | None = Field(None, ge=0)
    zinc_mg: float | None = Field(None, ge=0)
    selenium_mcg: float | None = Field(None, ge=0)
    copper_mcg: float | None = Field(None, ge=0)
    manganese_mg: float | None = Field(None, ge=0)
    iodine_mcg: float | None = Field(None, ge=0)

    # Other
    omega3_mg: float | None = Field(None, ge=0)
    biotin_mcg: float | None = Field(None, ge=0)
    choline_mg: float | None = Field(None, ge=0)


class SupplementCreate(SupplementNutrients):
    """Request body for creating a supplement."""

    name: str = Field(..., min_length=1, max_length=200)
    brand: str | None = Field(None, max_length=200)
    serving_size: str | None = Field(None, max_length=100)  # e.g., "1 tablet"
    notes: str | None = None


class SupplementUpdate(BaseModel):
    """Request body for updating a supplement."""

    name: str | None = Field(None, min_length=1, max_length=200)
    brand: str | None = None
    serving_size: str | None = None
    notes: str | None = None
    is_active: bool | None = None

    # Nutrients (all optional for partial updates)
    vitamin_a_mcg: float | None = None
    vitamin_c_mg: float | None = None
    vitamin_d_mcg: float | None = None
    vitamin_e_mg: float | None = None
    vitamin_k_mcg: float | None = None
    vitamin_b1_mg: float | None = None
    vitamin_b2_mg: float | None = None
    vitamin_b3_mg: float | None = None
    vitamin_b6_mg: float | None = None
    vitamin_b9_mcg: float | None = None
    vitamin_b12_mcg: float | None = None
    calcium_mg: float | None = None
    iron_mg: float | None = None
    magnesium_mg: float | None = None
    phosphorus_mg: float | None = None
    potassium_mg: float | None = None
    zinc_mg: float | None = None
    selenium_mcg: float | None = None
    copper_mcg: float | None = None
    manganese_mg: float | None = None
    iodine_mcg: float | None = None
    omega3_mg: float | None = None
    biotin_mcg: float | None = None
    choline_mg: float | None = None


class SupplementResponse(SupplementNutrients):
    """Response body for a supplement."""

    id: str
    user_id: str
    name: str
    brand: str | None
    serving_size: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplementLogCreate(BaseModel):
    """Request body for logging a supplement intake."""

    supplement_id: str
    servings: float = Field(1.0, gt=0)
    logged_at: datetime | None = None
    notes: str | None = None


class SupplementLogResponse(BaseModel):
    """Response body for a supplement log entry."""

    id: str
    user_id: str
    supplement_id: str
    supplement_name: str  # Included for convenience
    servings: float
    logged_at: datetime
    notes: str | None
    created_at: datetime

    # Calculated nutrients (servings * supplement nutrients)
    total_vitamin_d_mcg: float | None = None
    total_vitamin_c_mg: float | None = None
    total_calcium_mg: float | None = None
    total_iron_mg: float | None = None

    class Config:
        from_attributes = True


class TodaySupplementSummary(BaseModel):
    """Summary of supplements taken today."""

    total_logs: int
    supplements_taken: list[str]  # Names of supplements taken

    # Totals from all supplements today
    total_vitamin_a_mcg: float = 0
    total_vitamin_c_mg: float = 0
    total_vitamin_d_mcg: float = 0
    total_vitamin_e_mg: float = 0
    total_vitamin_k_mcg: float = 0
    total_vitamin_b1_mg: float = 0
    total_vitamin_b2_mg: float = 0
    total_vitamin_b3_mg: float = 0
    total_vitamin_b6_mg: float = 0
    total_vitamin_b9_mcg: float = 0
    total_vitamin_b12_mcg: float = 0
    total_calcium_mg: float = 0
    total_iron_mg: float = 0
    total_magnesium_mg: float = 0
    total_phosphorus_mg: float = 0
    total_potassium_mg: float = 0
    total_zinc_mg: float = 0
    total_selenium_mcg: float = 0
    total_copper_mcg: float = 0
    total_manganese_mg: float = 0
