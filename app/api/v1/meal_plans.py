"""Meal planning endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import MealPlan, MealPlanDay, GroceryList, UserProfile, get_db
from app.infrastructure.external.spoonacular import get_spoonacular_client
from app.infrastructure.external.unsplash import get_unsplash_client
from app.infrastructure.ai.gemini_client import GeminiClient
from app.config import settings

router = APIRouter()


async def enrich_meals_with_images(meals: list[dict], diet: str = None) -> list[dict]:
    """Enrich meals with images from Spoonacular."""
    client = get_spoonacular_client()
    enriched = []

    for meal in meals:
        name = meal.get("name", "")
        if name and not meal.get("image_url"):
            try:
                recipe = await client.search_recipe(name, diet)
                if recipe:
                    meal["image_url"] = recipe.get("image")
                    meal["ready_in_minutes"] = recipe.get("ready_in_minutes")
                    meal["servings"] = recipe.get("servings")
            except Exception as e:
                print(f"Failed to enrich meal {name}: {e}")
        enriched.append(meal)

    return enriched


async def generate_recipe_with_ai(meal_name: str, meal_type: str, user_profile: dict = None) -> dict:
    """Generate a personalized recipe using Gemini AI."""
    client = GeminiClient()

    # Build context from user profile
    context_parts = []
    if user_profile:
        if user_profile.get("diet_style"):
            context_parts.append(f"Diet: {user_profile['diet_style']}")
        if user_profile.get("allergies"):
            context_parts.append(f"Allergies to avoid: {', '.join(user_profile['allergies'])}")

    context = ". ".join(context_parts) if context_parts else "No dietary restrictions"

    prompt = f"""Generate a simple, healthy recipe for "{meal_name}" as a {meal_type}.

User context: {context}

Provide the response in this exact JSON format:
{{
    "name": "{meal_name}",
    "description": "Brief 1-2 sentence description",
    "prep_time_minutes": 10,
    "cook_time_minutes": 20,
    "servings": 2,
    "difficulty": "easy",
    "ingredients": [
        {{"item": "ingredient name", "amount": "1 cup", "notes": "optional prep notes"}}
    ],
    "instructions": [
        "Step 1: Do this...",
        "Step 2: Then do this..."
    ],
    "tips": ["Optional cooking tip"],
    "nutrition_notes": "Brief note about nutritional benefits"
}}

Keep the recipe simple with common ingredients. Make instructions clear and beginner-friendly."""

    try:
        response = await client.generate_text(prompt)
        # Parse JSON from response
        import json
        import re

        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            recipe_data = json.loads(json_match.group())
            return recipe_data
    except Exception as e:
        print(f"AI recipe generation error: {e}")

    # Return a basic fallback
    return {
        "name": meal_name,
        "description": f"A delicious {meal_type} meal",
        "prep_time_minutes": 15,
        "cook_time_minutes": 20,
        "servings": 2,
        "difficulty": "easy",
        "ingredients": [],
        "instructions": ["Recipe instructions not available. Please search online for preparation details."],
        "tips": [],
        "nutrition_notes": ""
    }


# MARK: - Schemas

class MealPlanDayResponse(BaseModel):
    id: str
    date: datetime
    day_number: int
    meals: list[dict]
    total_calories: int | None
    total_protein: float | None
    total_carbs: float | None
    total_fat: float | None
    notes: str | None

    class Config:
        from_attributes = True


class MealPlanResponse(BaseModel):
    id: str
    name: str
    start_date: datetime
    end_date: datetime
    goal: str | None
    daily_calorie_target: int | None
    daily_protein_target: float | None
    daily_carbs_target: float | None
    daily_fat_target: float | None
    preferences: dict | None
    is_active: bool
    created_at: datetime
    days: list[MealPlanDayResponse] = []

    class Config:
        from_attributes = True


class MealPlanSummaryResponse(BaseModel):
    id: str
    name: str
    start_date: datetime
    end_date: datetime
    goal: str | None
    is_active: bool
    day_count: int

    class Config:
        from_attributes = True


class GroceryItemUpdate(BaseModel):
    item_index: int
    checked: bool


class GroceryListResponse(BaseModel):
    id: str
    name: str
    meal_plan_id: str | None
    items: list[dict]
    created_at: datetime

    class Config:
        from_attributes = True


# MARK: - Meal Plan Endpoints

@router.get("", response_model=list[MealPlanSummaryResponse])
async def get_meal_plans(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = True,
) -> list[MealPlanSummaryResponse]:
    """Get all meal plans for the current user."""
    query = (
        select(MealPlan)
        .where(MealPlan.user_id == current_user.id)
        .options(selectinload(MealPlan.days))
    )

    if active_only:
        query = query.where(MealPlan.is_active == True)

    query = query.order_by(MealPlan.created_at.desc())

    result = await db.execute(query)
    plans = result.scalars().all()

    return [
        MealPlanSummaryResponse(
            id=plan.id,
            name=plan.name,
            start_date=plan.start_date,
            end_date=plan.end_date,
            goal=plan.goal,
            is_active=plan.is_active,
            day_count=len(plan.days),
        )
        for plan in plans
    ]


@router.get("/active", response_model=MealPlanResponse | None)
async def get_active_meal_plan(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealPlanResponse | None:
    """Get the currently active meal plan with all days."""
    result = await db.execute(
        select(MealPlan)
        .where(MealPlan.user_id == current_user.id)
        .where(MealPlan.is_active == True)
        .options(selectinload(MealPlan.days))
        .order_by(MealPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        return None

    return MealPlanResponse(
        id=plan.id,
        name=plan.name,
        start_date=plan.start_date,
        end_date=plan.end_date,
        goal=plan.goal,
        daily_calorie_target=plan.daily_calorie_target,
        daily_protein_target=plan.daily_protein_target,
        daily_carbs_target=plan.daily_carbs_target,
        daily_fat_target=plan.daily_fat_target,
        preferences=plan.preferences,
        is_active=plan.is_active,
        created_at=plan.created_at,
        days=[
            MealPlanDayResponse(
                id=day.id,
                date=day.date,
                day_number=day.day_number,
                meals=day.meals,
                total_calories=day.total_calories,
                total_protein=day.total_protein,
                total_carbs=day.total_carbs,
                total_fat=day.total_fat,
                notes=day.notes,
            )
            for day in sorted(plan.days, key=lambda d: d.day_number)
        ],
    )


@router.get("/today", response_model=MealPlanDayResponse | None)
async def get_todays_meals(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealPlanDayResponse | None:
    """Get today's meals from the active meal plan with images enriched."""
    from datetime import timezone

    result = await db.execute(
        select(MealPlan)
        .where(MealPlan.user_id == current_user.id)
        .where(MealPlan.is_active == True)
        .options(selectinload(MealPlan.days))
        .order_by(MealPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        return None

    # Find today's day
    today = datetime.now(timezone.utc).date()
    today_day = None
    for day in plan.days:
        if day.date.date() == today:
            today_day = day
            break

    # If no exact match, find by day number from plan start
    if not today_day and plan.days:
        days_since_start = (today - plan.start_date.date()).days + 1
        for day in plan.days:
            if day.day_number == days_since_start:
                today_day = day
                break

    if not today_day:
        return None

    # Get diet preference for better image matching
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    diet = profile.diet_style if profile else None

    # Enrich meals with images from Spoonacular
    enriched_meals = await enrich_meals_with_images(today_day.meals or [], diet)

    return MealPlanDayResponse(
        id=today_day.id,
        date=today_day.date,
        day_number=today_day.day_number,
        meals=enriched_meals,
        total_calories=today_day.total_calories,
        total_protein=today_day.total_protein,
        total_carbs=today_day.total_carbs,
        total_fat=today_day.total_fat,
        notes=today_day.notes,
    )


# MARK: - Grocery List Endpoints (must be before /{plan_id} to avoid route conflicts)

@router.get("/grocery-lists", response_model=list[GroceryListResponse])
async def get_grocery_lists(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[GroceryListResponse]:
    """Get all grocery lists for the current user."""
    result = await db.execute(
        select(GroceryList)
        .where(GroceryList.user_id == current_user.id)
        .order_by(GroceryList.created_at.desc())
    )
    lists = result.scalars().all()

    return [
        GroceryListResponse(
            id=gl.id,
            name=gl.name,
            meal_plan_id=gl.meal_plan_id,
            items=gl.items,
            created_at=gl.created_at,
        )
        for gl in lists
    ]


@router.get("/grocery-lists/{list_id}", response_model=GroceryListResponse)
async def get_grocery_list(
    list_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroceryListResponse:
    """Get a specific grocery list."""
    result = await db.execute(
        select(GroceryList)
        .where(GroceryList.id == list_id)
        .where(GroceryList.user_id == current_user.id)
    )
    gl = result.scalar_one_or_none()

    if not gl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grocery list not found",
        )

    return GroceryListResponse(
        id=gl.id,
        name=gl.name,
        meal_plan_id=gl.meal_plan_id,
        items=gl.items,
        created_at=gl.created_at,
    )


@router.patch("/grocery-lists/{list_id}/item")
async def update_grocery_item(
    list_id: str,
    update: GroceryItemUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Toggle checked status of a grocery item."""
    result = await db.execute(
        select(GroceryList)
        .where(GroceryList.id == list_id)
        .where(GroceryList.user_id == current_user.id)
    )
    gl = result.scalar_one_or_none()

    if not gl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grocery list not found",
        )

    if update.item_index < 0 or update.item_index >= len(gl.items):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid item index",
        )

    # Update the item
    items = gl.items.copy()
    items[update.item_index]["checked"] = update.checked
    gl.items = items

    await db.commit()

    return {"success": True}


@router.delete("/grocery-lists/{list_id}")
async def delete_grocery_list(
    list_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a grocery list."""
    result = await db.execute(
        select(GroceryList)
        .where(GroceryList.id == list_id)
        .where(GroceryList.user_id == current_user.id)
    )
    gl = result.scalar_one_or_none()

    if not gl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grocery list not found",
        )

    await db.delete(gl)
    await db.commit()

    return {"success": True}


# MARK: - Meal Plan Detail Endpoints

@router.get("/{plan_id}", response_model=MealPlanResponse)
async def get_meal_plan(
    plan_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealPlanResponse:
    """Get a specific meal plan with all days."""
    result = await db.execute(
        select(MealPlan)
        .where(MealPlan.id == plan_id)
        .where(MealPlan.user_id == current_user.id)
        .options(selectinload(MealPlan.days))
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal plan not found",
        )

    return MealPlanResponse(
        id=plan.id,
        name=plan.name,
        start_date=plan.start_date,
        end_date=plan.end_date,
        goal=plan.goal,
        daily_calorie_target=plan.daily_calorie_target,
        daily_protein_target=plan.daily_protein_target,
        daily_carbs_target=plan.daily_carbs_target,
        daily_fat_target=plan.daily_fat_target,
        preferences=plan.preferences,
        is_active=plan.is_active,
        created_at=plan.created_at,
        days=[
            MealPlanDayResponse(
                id=day.id,
                date=day.date,
                day_number=day.day_number,
                meals=day.meals,
                total_calories=day.total_calories,
                total_protein=day.total_protein,
                total_carbs=day.total_carbs,
                total_fat=day.total_fat,
                notes=day.notes,
            )
            for day in sorted(plan.days, key=lambda d: d.day_number)
        ],
    )


@router.delete("/{plan_id}")
async def delete_meal_plan(
    plan_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a meal plan."""
    result = await db.execute(
        select(MealPlan)
        .where(MealPlan.id == plan_id)
        .where(MealPlan.user_id == current_user.id)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal plan not found",
        )

    await db.delete(plan)
    await db.commit()

    return {"success": True}


@router.patch("/{plan_id}/deactivate")
async def deactivate_meal_plan(
    plan_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Deactivate a meal plan."""
    result = await db.execute(
        select(MealPlan)
        .where(MealPlan.id == plan_id)
        .where(MealPlan.user_id == current_user.id)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal plan not found",
        )

    plan.is_active = False
    await db.commit()

    return {"success": True}


# MARK: - Recipe Generation Endpoint

class RecipeRequest(BaseModel):
    meal_name: str
    meal_type: str = "lunch"  # breakfast, lunch, dinner, snack


class RecipeResponse(BaseModel):
    name: str
    description: str
    prep_time_minutes: int
    cook_time_minutes: int
    servings: int
    difficulty: str
    ingredients: list[dict]
    instructions: list[str]
    tips: list[str]
    nutrition_notes: str
    image_url: str | None = None


@router.post("/recipe", response_model=RecipeResponse)
async def get_meal_recipe(
    request: RecipeRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecipeResponse:
    """Generate a personalized recipe for a meal using AI."""
    # Get user profile for dietary preferences
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()

    user_profile = None
    if profile:
        user_profile = {
            "diet_style": profile.diet_style,
            "allergies": profile.allergies or [],
        }

    # Generate recipe with AI
    recipe = await generate_recipe_with_ai(
        meal_name=request.meal_name,
        meal_type=request.meal_type,
        user_profile=user_profile,
    )

    # Get image from Spoonacular
    image_url = None
    try:
        spoonacular = get_spoonacular_client()
        diet = profile.diet_style if profile else None
        spoon_recipe = await spoonacular.search_recipe(request.meal_name, diet)
        if spoon_recipe:
            image_url = spoon_recipe.get("image")
    except Exception as e:
        print(f"Failed to get meal image: {e}")

    return RecipeResponse(
        name=recipe.get("name", request.meal_name),
        description=recipe.get("description", ""),
        prep_time_minutes=recipe.get("prep_time_minutes", 15),
        cook_time_minutes=recipe.get("cook_time_minutes", 20),
        servings=recipe.get("servings", 2),
        difficulty=recipe.get("difficulty", "easy"),
        ingredients=recipe.get("ingredients", []),
        instructions=recipe.get("instructions", []),
        tips=recipe.get("tips", []),
        nutrition_notes=recipe.get("nutrition_notes", ""),
        image_url=image_url,
    )


# MARK: - Food Search Endpoint

class FoodSearchResult(BaseModel):
    """Search result for food database lookup."""
    name: str
    calories: int | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    image_url: str | None = None
    image_source: str | None = None  # "unsplash" or "spoonacular"
    ready_in_minutes: int | None = None
    servings: int | None = None


@router.get("/foods/search", response_model=list[FoodSearchResult])
async def search_foods(
    query: str,
    diet: str | None = None,
    limit: int = 20,
) -> list[FoodSearchResult]:
    """
    Search for foods/meals by name.

    Used for manual meal plan creation - returns foods with
    calorie info and high-quality images.
    """
    spoonacular = get_spoonacular_client()
    unsplash = get_unsplash_client()

    results = []

    # Search Spoonacular for nutrition data
    spoon_result = await spoonacular.search_recipe(query, diet)
    if spoon_result:
        # Try to get a better image from Unsplash
        unsplash_image = await unsplash.search_food_image(query)

        results.append(FoodSearchResult(
            name=spoon_result.get("title", query),
            calories=spoon_result.get("calories"),
            protein_g=spoon_result.get("protein"),
            carbs_g=spoon_result.get("carbs"),
            fat_g=spoon_result.get("fat"),
            image_url=unsplash_image.get("url_regular") if unsplash_image else spoon_result.get("image"),
            image_source="unsplash" if unsplash_image else "spoonacular",
            ready_in_minutes=spoon_result.get("ready_in_minutes"),
            servings=spoon_result.get("servings"),
        ))

    return results[:limit]


# MARK: - Manual Meal Plan Creation

class PlannedMealCreate(BaseModel):
    """Meal data for manual plan creation."""
    type: str  # breakfast, lunch, dinner, snack
    name: str
    description: str | None = None
    calories: int = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0


class MealPlanDayCreate(BaseModel):
    """Day data for manual plan creation."""
    day_number: int
    meals: list[PlannedMealCreate] = []
    notes: str | None = None


class MealPlanCreate(BaseModel):
    """Request body for manual meal plan creation."""
    name: str
    duration_days: int = 7
    goal: str | None = None  # "weight_loss", "muscle_gain", "maintenance"
    daily_calorie_target: int | None = None
    daily_protein_target: float | None = None
    daily_carbs_target: float | None = None
    daily_fat_target: float | None = None
    days: list[MealPlanDayCreate] = []


@router.post("", response_model=MealPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_meal_plan(
    plan_data: MealPlanCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealPlanResponse:
    """
    Create a meal plan manually (bypassing AI generation).

    Used for the "Manual" tab in plan creation sheet.
    Meals will be enriched with high-quality images automatically.
    """
    import uuid
    from datetime import timedelta, timezone

    # Deactivate any existing active plans
    result = await db.execute(
        select(MealPlan)
        .where(MealPlan.user_id == current_user.id)
        .where(MealPlan.is_active == True)
    )
    existing_plans = result.scalars().all()
    for existing in existing_plans:
        existing.is_active = False

    # Calculate start and end dates
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=plan_data.duration_days)

    # Create the new plan
    plan = MealPlan(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=plan_data.name,
        start_date=start_date,
        end_date=end_date,
        goal=plan_data.goal,
        daily_calorie_target=plan_data.daily_calorie_target,
        daily_protein_target=plan_data.daily_protein_target,
        daily_carbs_target=plan_data.daily_carbs_target,
        daily_fat_target=plan_data.daily_fat_target,
        is_active=True,
    )
    db.add(plan)

    # Get user diet preference for image enrichment
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    diet = profile.diet_style if profile else None

    # Create meal plan days with enriched images
    created_days = []
    unsplash = get_unsplash_client()

    for day_data in plan_data.days:
        # Convert meals to dict format and enrich with images
        meals = []
        total_calories = 0
        total_protein = 0.0
        total_carbs = 0.0
        total_fat = 0.0

        for meal in day_data.meals:
            meal_dict = meal.model_dump()

            # Try to get a high-quality image from Unsplash
            if not meal_dict.get("image_url"):
                unsplash_image = await unsplash.search_food_image(meal.name)
                if unsplash_image:
                    meal_dict["image_url"] = unsplash_image.get("url_regular")
                    meal_dict["image_source"] = "unsplash"
                else:
                    # Fall back to Spoonacular
                    spoon_result = await get_spoonacular_client().search_recipe(meal.name, diet)
                    if spoon_result:
                        meal_dict["image_url"] = spoon_result.get("image")
                        meal_dict["image_source"] = "spoonacular"

            meals.append(meal_dict)
            total_calories += meal.calories
            total_protein += meal.protein_g
            total_carbs += meal.carbs_g
            total_fat += meal.fat_g

        day = MealPlanDay(
            id=str(uuid.uuid4()),
            meal_plan_id=plan.id,
            date=start_date + timedelta(days=day_data.day_number - 1),
            day_number=day_data.day_number,
            meals=meals,
            total_calories=total_calories,
            total_protein=total_protein,
            total_carbs=total_carbs,
            total_fat=total_fat,
            notes=day_data.notes,
        )
        db.add(day)
        created_days.append(day)

    await db.commit()
    await db.refresh(plan)

    return MealPlanResponse(
        id=plan.id,
        name=plan.name,
        start_date=plan.start_date,
        end_date=plan.end_date,
        goal=plan.goal,
        daily_calorie_target=plan.daily_calorie_target,
        daily_protein_target=plan.daily_protein_target,
        daily_carbs_target=plan.daily_carbs_target,
        daily_fat_target=plan.daily_fat_target,
        preferences=plan.preferences,
        is_active=plan.is_active,
        created_at=plan.created_at,
        days=[
            MealPlanDayResponse(
                id=day.id,
                date=day.date,
                day_number=day.day_number,
                meals=day.meals,
                total_calories=day.total_calories,
                total_protein=day.total_protein,
                total_carbs=day.total_carbs,
                total_fat=day.total_fat,
                notes=day.notes,
            )
            for day in sorted(created_days, key=lambda d: d.day_number)
        ],
    )
