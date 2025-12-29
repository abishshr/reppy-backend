"""Pydantic schemas for API request/response validation."""

from app.schemas.auth import AppleSignInRequest, AuthResponse, TokenPayload
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse, ToolCallResult
from app.schemas.food import (
    BarcodeLookupResponse,
    FoodItemCreate,
    FoodItemResponse,
    FoodSearchResponse,
    RecentFoodsResponse,
)
from app.schemas.meal import (
    MealItem,
    MealLogCreate,
    MealLogResponse,
    MealSuggestion,
)
from app.schemas.profile import ProfileCreate, ProfileResponse, ProfileUpdate
from app.schemas.workout import (
    Exercise,
    PRInfo,
    WorkoutLogCreate,
    WorkoutLogResponse,
    WorkoutSuggestion,
)
from app.schemas.activity import (
    ActivityResponse,
    ActivitySummary,
    StepsSyncRequest,
)

__all__ = [
    "ActivityResponse",
    "ActivitySummary",
    "AppleSignInRequest",
    "AuthResponse",
    "BarcodeLookupResponse",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "Exercise",
    "FoodItemCreate",
    "FoodItemResponse",
    "FoodSearchResponse",
    "MealItem",
    "MealLogCreate",
    "MealLogResponse",
    "MealSuggestion",
    "PRInfo",
    "ProfileCreate",
    "ProfileResponse",
    "ProfileUpdate",
    "RecentFoodsResponse",
    "StepsSyncRequest",
    "TokenPayload",
    "ToolCallResult",
    "WorkoutLogCreate",
    "WorkoutLogResponse",
    "WorkoutSuggestion",
]
