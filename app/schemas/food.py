"""Food database schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FoodItemBase(BaseModel):
    """Base fields for food items."""

    name: str = Field(..., min_length=1, max_length=500)
    brand: Optional[str] = Field(None, max_length=255)
    barcode: Optional[str] = Field(None, max_length=50)

    # Serving info
    serving_size: Optional[str] = Field(None, max_length=100)
    serving_size_g: Optional[float] = Field(None, ge=0)

    # Nutrition per serving
    calories: Optional[float] = Field(None, ge=0)
    protein_g: Optional[float] = Field(None, ge=0)
    carbs_g: Optional[float] = Field(None, ge=0)
    fat_g: Optional[float] = Field(None, ge=0)
    fiber_g: Optional[float] = Field(None, ge=0)
    sugar_g: Optional[float] = Field(None, ge=0)
    sodium_mg: Optional[float] = Field(None, ge=0)
    saturated_fat_g: Optional[float] = Field(None, ge=0)
    cholesterol_mg: Optional[float] = Field(None, ge=0)


class FoodItemCreate(FoodItemBase):
    """Request body for creating a user food."""

    pass


class FoodItemResponse(FoodItemBase):
    """Response for a food item."""

    id: str
    external_id: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    source: str  # open_food_facts, usda, user_created
    is_verified: bool
    created_at: datetime

    # Testosterone impact analysis (for male users)
    testosterone_impact: Optional[str] = None  # "boosts", "reduces", "neutral"

    class Config:
        from_attributes = True


class FoodSearchResponse(BaseModel):
    """Response for food search."""

    foods: list[FoodItemResponse]
    total: int
    query: str


class BarcodeLookupResponse(BaseModel):
    """Response for barcode lookup."""

    found: bool
    food: Optional[FoodItemResponse] = None
    barcode: str


class FoodItemWithServings(FoodItemResponse):
    """Food item with serving quantity for meal logging."""

    quantity: float = Field(1.0, ge=0)
    unit: str = "serving"

    # Calculated totals based on quantity
    total_calories: Optional[float] = None
    total_protein_g: Optional[float] = None
    total_carbs_g: Optional[float] = None
    total_fat_g: Optional[float] = None


class QuickAddFood(BaseModel):
    """Quick add food without full details (AI estimation)."""

    name: str = Field(..., min_length=1)
    calories: int = Field(..., ge=0)
    protein_g: Optional[float] = Field(None, ge=0)
    carbs_g: Optional[float] = Field(None, ge=0)
    fat_g: Optional[float] = Field(None, ge=0)


class NutritionSummary(BaseModel):
    """Nutrition summary for a food or meal."""

    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None


class RecentFoodsResponse(BaseModel):
    """Response for recent/frequent foods."""

    foods: list[FoodItemResponse]
