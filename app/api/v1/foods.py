"""Food database endpoints for searching and managing foods."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import get_db
from app.infrastructure.database.models import UserProfile
from app.services.food_database import FoodDatabaseService, get_food_database_service
from app.services.testosterone_analyzer import testosterone_analyzer
from app.schemas.food import (
    FoodItemCreate,
    FoodItemResponse,
    FoodSearchResponse,
    BarcodeLookupResponse,
    RecentFoodsResponse,
)

router = APIRouter()


def get_food_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FoodDatabaseService:
    """Dependency to get food database service."""
    return get_food_database_service(db)


async def is_user_male(db: AsyncSession, user_id: str) -> bool:
    """Check if user is male for testosterone feature."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    return profile is not None and profile.sex == "male"


def enrich_food_with_testosterone(food: FoodItemResponse) -> FoodItemResponse:
    """Add testosterone impact analysis to a food item."""
    nutrients = {
        "protein_g": food.protein_g,
        "sugar_g": food.sugar_g,
        "fat_g": food.fat_g,
    }
    impact = testosterone_analyzer.analyze_food(food.name, nutrients)
    food.testosterone_impact = impact
    return food


@router.get("/search", response_model=FoodSearchResponse)
async def search_foods(
    current_user: CurrentUser,
    food_service: Annotated[FoodDatabaseService, Depends(get_food_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str = Query(..., min_length=2, max_length=100, description="Search query"),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum results"),
) -> FoodSearchResponse:
    """
    Search for foods across all databases.

    Searches:
    1. Local cached foods (fastest)
    2. Open Food Facts (branded products with barcodes)
    3. USDA FoodData Central (generic foods, accurate nutrition)

    Results are cached locally for faster future searches.
    For male users, includes testosterone impact analysis.
    """
    foods = await food_service.search_foods(
        query=q,
        limit=limit,
        include_user_foods=True,
        user_id=current_user.id,
    )

    food_responses = [FoodItemResponse.model_validate(f) for f in foods]

    # Add testosterone impact for male users
    if await is_user_male(db, current_user.id):
        food_responses = [enrich_food_with_testosterone(f) for f in food_responses]

    return FoodSearchResponse(
        foods=food_responses,
        total=len(food_responses),
        query=q,
    )


@router.get("/barcode/{barcode}", response_model=BarcodeLookupResponse)
async def lookup_barcode(
    barcode: str,
    current_user: CurrentUser,
    food_service: Annotated[FoodDatabaseService, Depends(get_food_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BarcodeLookupResponse:
    """
    Look up a food by barcode.

    Supports:
    - EAN-13 (international)
    - UPC-A (US/Canada)
    - EAN-8 (short form)

    Searches:
    1. Local cache (fastest)
    2. Open Food Facts (best barcode coverage, 2M+ products)
    3. USDA FoodData Central (branded foods with GTIN/UPC)
    """
    # Validate barcode format (basic check)
    if not barcode.isdigit() or len(barcode) not in [8, 12, 13, 14]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid barcode format. Expected 8, 12, 13, or 14 digits.",
        )

    food = await food_service.get_by_barcode(barcode)

    if food:
        food_response = FoodItemResponse.model_validate(food)
        # Add testosterone impact for male users
        if await is_user_male(db, current_user.id):
            food_response = enrich_food_with_testosterone(food_response)
        return BarcodeLookupResponse(
            found=True,
            food=food_response,
            barcode=barcode,
        )
    else:
        return BarcodeLookupResponse(
            found=False,
            food=None,
            barcode=barcode,
        )


@router.get("/recent", response_model=RecentFoodsResponse)
async def get_recent_foods(
    current_user: CurrentUser,
    food_service: Annotated[FoodDatabaseService, Depends(get_food_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=50),
) -> RecentFoodsResponse:
    """
    Get the user's recently logged foods.

    Returns foods ordered by most recently logged first.
    """
    foods = await food_service.get_recent_foods(
        user_id=current_user.id,
        limit=limit,
    )

    food_responses = [FoodItemResponse.model_validate(f) for f in foods]

    # Add testosterone impact for male users
    if await is_user_male(db, current_user.id):
        food_responses = [enrich_food_with_testosterone(f) for f in food_responses]

    return RecentFoodsResponse(foods=food_responses)


@router.get("/frequent", response_model=RecentFoodsResponse)
async def get_frequent_foods(
    current_user: CurrentUser,
    food_service: Annotated[FoodDatabaseService, Depends(get_food_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=50),
) -> RecentFoodsResponse:
    """
    Get the user's most frequently logged foods.

    Returns foods ordered by number of times logged, descending.
    """
    foods = await food_service.get_frequent_foods(
        user_id=current_user.id,
        limit=limit,
    )

    food_responses = [FoodItemResponse.model_validate(f) for f in foods]

    # Add testosterone impact for male users
    if await is_user_male(db, current_user.id):
        food_responses = [enrich_food_with_testosterone(f) for f in food_responses]

    return RecentFoodsResponse(foods=food_responses)


@router.get("/my-foods", response_model=RecentFoodsResponse)
async def get_my_foods(
    current_user: CurrentUser,
    food_service: Annotated[FoodDatabaseService, Depends(get_food_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
) -> RecentFoodsResponse:
    """
    Get all custom foods created by the current user.

    Returns foods ordered by most recently created first.
    """
    foods = await food_service.get_user_foods(
        user_id=current_user.id,
        limit=limit,
    )

    food_responses = [FoodItemResponse.model_validate(f) for f in foods]

    # Add testosterone impact for male users
    if await is_user_male(db, current_user.id):
        food_responses = [enrich_food_with_testosterone(f) for f in food_responses]

    return RecentFoodsResponse(foods=food_responses)


@router.delete("/{food_id}", status_code=status.HTTP_200_OK)
async def delete_food(
    food_id: str,
    current_user: CurrentUser,
    food_service: Annotated[FoodDatabaseService, Depends(get_food_service)],
) -> dict:
    """Delete a custom food item. Only the creator can delete their foods."""
    food = await food_service.get_by_id(food_id)

    if not food:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Food not found",
        )

    # Only allow deletion of user-created foods
    if food.source != "user_created" or str(food.created_by_user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own custom foods",
        )

    await food_service.delete_food(food_id)
    return {"success": True}


@router.get("/{food_id}", response_model=FoodItemResponse)
async def get_food(
    food_id: str,
    current_user: CurrentUser,
    food_service: Annotated[FoodDatabaseService, Depends(get_food_service)],
) -> FoodItemResponse:
    """Get a specific food item by ID."""
    food = await food_service.get_by_id(food_id)

    if not food:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Food not found",
        )

    return FoodItemResponse.model_validate(food)


@router.post("/", response_model=FoodItemResponse, status_code=status.HTTP_201_CREATED)
async def create_food(
    current_user: CurrentUser,
    food_data: FoodItemCreate,
    food_service: Annotated[FoodDatabaseService, Depends(get_food_service)],
) -> FoodItemResponse:
    """
    Create a custom food item.

    Use this when a food isn't found in the database.
    User-created foods are saved for future use.
    """
    food = await food_service.create_user_food(
        user_id=current_user.id,
        name=food_data.name,
        brand=food_data.brand,
        barcode=food_data.barcode,
        serving_size=food_data.serving_size,
        serving_size_g=food_data.serving_size_g,
        calories=food_data.calories,
        protein_g=food_data.protein_g,
        carbs_g=food_data.carbs_g,
        fat_g=food_data.fat_g,
        fiber_g=food_data.fiber_g,
        sugar_g=food_data.sugar_g,
        sodium_mg=food_data.sodium_mg,
        saturated_fat_g=food_data.saturated_fat_g,
        cholesterol_mg=food_data.cholesterol_mg,
    )

    return FoodItemResponse.model_validate(food)


@router.post("/{food_id}/log", status_code=status.HTTP_204_NO_CONTENT)
async def record_food_log(
    food_id: str,
    current_user: CurrentUser,
    food_service: Annotated[FoodDatabaseService, Depends(get_food_service)],
) -> None:
    """
    Record that the user logged this food.

    This updates the recent/frequent foods list for the user.
    Call this when adding a food to a meal.
    """
    # Verify food exists
    food = await food_service.get_by_id(food_id)
    if not food:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Food not found",
        )

    await food_service.record_food_usage(
        user_id=current_user.id,
        food_item_id=food_id,
    )
