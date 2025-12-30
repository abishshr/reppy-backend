"""Meal planning tools for AI-generated meal plans."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import MealPlan, MealPlanDay, GroceryList, UserProfile
from app.infrastructure.redis.client import redis_client
from app.infrastructure.external.spoonacular import get_spoonacular_client
from app.infrastructure.ai.gemini_client import GeminiClient
from app.mcp.tools.base import BaseTool, ToolResult


async def generate_recipe_for_meal(meal_name: str, meal_type: str, diet: str = None, allergies: list = None) -> dict:
    """Generate a recipe for a meal using Gemini AI."""
    client = GeminiClient()

    # Build context
    context_parts = []
    if diet:
        context_parts.append(f"Diet: {diet}")
    if allergies:
        context_parts.append(f"Allergies to avoid: {', '.join(allergies)}")

    context = ". ".join(context_parts) if context_parts else "No dietary restrictions"

    prompt = f"""Generate a simple recipe for "{meal_name}" as a {meal_type}.

User context: {context}

Respond with ONLY valid JSON (no markdown):
{{"ingredients":[{{"item":"name","amount":"quantity","notes":"optional"}}],"instructions":["Step 1...","Step 2..."],"prep_time_min":10,"cook_time_min":15,"difficulty":"easy","tips":["tip1"],"nutrition_notes":"brief note"}}"""

    try:
        response = await client.generate_text(prompt)
        import json
        import re

        # Extract JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"[MealPlanTools] Recipe generation error for {meal_name}: {e}")

    return {}


async def enrich_meal_with_recipe_and_image(meal: dict, diet: str = None, allergies: list = None) -> dict:
    """Enrich a single meal with recipe and image."""
    meal_name = meal.get("name", "")
    meal_type = meal.get("type", "lunch")

    # Run recipe generation and image fetch in parallel
    recipe_task = generate_recipe_for_meal(meal_name, meal_type, diet, allergies)

    spoonacular = get_spoonacular_client()
    image_task = spoonacular.search_recipe(meal_name, diet)

    recipe_data, spoon_data = await asyncio.gather(recipe_task, image_task, return_exceptions=True)

    # Add recipe data
    if isinstance(recipe_data, dict) and recipe_data:
        meal["ingredients"] = recipe_data.get("ingredients", [])
        meal["instructions"] = recipe_data.get("instructions", [])
        meal["prep_time_min"] = recipe_data.get("prep_time_min")
        meal["cook_time_min"] = recipe_data.get("cook_time_min")
        meal["difficulty"] = recipe_data.get("difficulty", "easy")
        meal["tips"] = recipe_data.get("tips", [])
        meal["nutrition_notes"] = recipe_data.get("nutrition_notes", "")

    # Add image data
    if isinstance(spoon_data, dict) and spoon_data:
        meal["image_url"] = spoon_data.get("image")
        meal["ready_in_minutes"] = spoon_data.get("ready_in_minutes")
        meal["servings"] = spoon_data.get("servings")

    return meal


async def enrich_all_meals(plan_data: list, diet: str = None, allergies: list = None) -> list:
    """Enrich all meals in the plan with recipes and images."""
    print(f"[MealPlanTools] Enriching {len(plan_data)} days with recipes and images...")

    # Collect all meals to enrich
    all_tasks = []
    meal_locations = []  # (day_idx, meal_idx) to track where to put results

    for day_idx, day in enumerate(plan_data):
        meals = day.get("meals", [])
        for meal_idx, meal in enumerate(meals):
            task = enrich_meal_with_recipe_and_image(meal, diet, allergies)
            all_tasks.append(task)
            meal_locations.append((day_idx, meal_idx))

    # Run all enrichments in parallel (with some concurrency limit)
    # Process in batches of 5 to avoid rate limiting
    batch_size = 5
    enriched_meals = []

    for i in range(0, len(all_tasks), batch_size):
        batch = all_tasks[i:i + batch_size]
        batch_results = await asyncio.gather(*batch, return_exceptions=True)
        enriched_meals.extend(batch_results)

        # Small delay between batches to avoid rate limiting
        if i + batch_size < len(all_tasks):
            await asyncio.sleep(0.5)

    # Put enriched meals back into plan_data
    for (day_idx, meal_idx), enriched_meal in zip(meal_locations, enriched_meals):
        if isinstance(enriched_meal, dict):
            plan_data[day_idx]["meals"][meal_idx] = enriched_meal

    print(f"[MealPlanTools] Enrichment complete for {len(enriched_meals)} meals")
    return plan_data


class GenerateMealPlanTool(BaseTool):
    """Generate a personalized meal plan based on user's profile and goals."""

    name = "generate_meal_plan"
    description = """Save a meal plan. The 'plan' parameter MUST contain complete meal data as a JSON array string.

REQUIRED: You must generate the meal content yourself and pass it in 'plan'.

Minimal example:
[{"day":1,"meals":[{"type":"breakfast","name":"Oatmeal","calories":350,"protein_g":12,"carbs_g":50,"fat_g":10},{"type":"lunch","name":"Chicken Salad","calories":500,"protein_g":40,"carbs_g":25,"fat_g":22},{"type":"dinner","name":"Salmon Rice","calories":650,"protein_g":45,"carbs_g":55,"fat_g":25},{"type":"snack","name":"Greek Yogurt","calories":200,"protein_g":15,"carbs_g":12,"fat_g":8}],"total_calories":1700,"total_protein":112}]

Each meal needs: type, name, calories, protein_g, carbs_g, fat_g
Optional: description, ingredients, instructions, prep_time_min, cook_time_min"""

    parameters = {
        "days": {
            "type": "integer",
            "description": "Number of days (1-14). Default: 7",
            "optional": True,
        },
        "focus": {
            "type": "string",
            "description": "Focus: balanced, high_protein, low_carb, vegetarian",
            "optional": True,
        },
        "plan": {
            "type": "string",
            "description": "REQUIRED: JSON array with meal data YOU generated. Must NOT be empty. Example: [{\"day\":1,\"meals\":[{\"type\":\"breakfast\",\"name\":\"Eggs\",\"calories\":300,\"protein_g\":20,\"carbs_g\":5,\"fat_g\":22}],\"total_calories\":1800}]",
        },
    }

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Store the generated meal plan."""
        import json as json_module

        print(f"[GenerateMealPlanTool] kwargs: {kwargs}")

        plan_raw = kwargs.get("plan", "[]")
        days = kwargs.get("days", 7)
        focus = kwargs.get("focus", "balanced")
        daily_calories = kwargs.get("daily_calories")

        print(f"[GenerateMealPlanTool] plan_raw type: {type(plan_raw)}, value preview: {str(plan_raw)[:200]}")

        # Parse plan data - could be a string or already a list
        if isinstance(plan_raw, str):
            try:
                plan_data = json_module.loads(plan_raw)
            except json_module.JSONDecodeError as e:
                print(f"[GenerateMealPlanTool] JSON decode error: {e}")
                return ToolResult(
                    success=False,
                    error=f"Invalid JSON in plan data: {str(e)}",
                )
        else:
            plan_data = plan_raw

        # Handle if plan_data is a dict with "days" key
        if isinstance(plan_data, dict) and "days" in plan_data:
            plan_data = plan_data["days"]

        print(f"[GenerateMealPlanTool] plan_data type: {type(plan_data)}, length: {len(plan_data) if isinstance(plan_data, list) else 'N/A'}")

        if not plan_data or (isinstance(plan_data, list) and len(plan_data) == 0):
            return ToolResult(
                success=False,
                error="ERROR: You passed an empty plan. You MUST generate meal data yourself. Create meals with name, calories, protein_g, carbs_g, fat_g for each day, then call this tool again with the complete plan data.",
            )

        # Get user profile for defaults
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == self.user_id)
        )
        profile = result.scalar_one_or_none()

        # Create meal plan
        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=days)

        meal_plan = MealPlan(
            user_id=self.user_id,
            name=f"{focus.replace('_', ' ').title()} Plan - {start_date.strftime('%b %d')}",
            start_date=start_date,
            end_date=end_date,
            goal=focus,
            daily_calorie_target=daily_calories or (profile.daily_calorie_target if profile else 2000),
            daily_protein_target=profile.daily_protein_target if profile else 150,
            daily_carbs_target=profile.daily_carbs_target if profile else 250,
            daily_fat_target=profile.daily_fat_target if profile else 65,
            preferences={
                "diet_style": profile.diet_style if profile else None,
                "allergies": profile.allergies if profile else [],
            },
        )
        self.db.add(meal_plan)
        await self.db.flush()

        # Create plan days
        for idx, day_data in enumerate(plan_data):
            # Handle if day_data is a string (shouldn't happen but just in case)
            if isinstance(day_data, str):
                try:
                    day_data = json_module.loads(day_data)
                except json_module.JSONDecodeError:
                    continue

            day_number = day_data.get("day", idx + 1) if isinstance(day_data, dict) else idx + 1
            meals = day_data.get("meals", []) if isinstance(day_data, dict) else []

            plan_day = MealPlanDay(
                meal_plan_id=meal_plan.id,
                date=start_date + timedelta(days=day_number - 1),
                day_number=day_number,
                meals=meals,
                total_calories=day_data.get("total_calories") if isinstance(day_data, dict) else None,
                total_protein=day_data.get("total_protein") if isinstance(day_data, dict) else None,
                total_carbs=day_data.get("total_carbs") if isinstance(day_data, dict) else None,
                total_fat=day_data.get("total_fat") if isinstance(day_data, dict) else None,
            )
            self.db.add(plan_day)

        await self.db.commit()

        # Build plan preview for UI display
        plan_preview = []
        for idx, day_data in enumerate(plan_data):
            if isinstance(day_data, dict):
                day_number = day_data.get("day", idx + 1)
                meals = day_data.get("meals", [])
                plan_preview.append({
                    "day_number": day_number,
                    "day_name": (start_date + timedelta(days=day_number - 1)).strftime("%A"),
                    "meals": [
                        {
                            "type": m.get("type", "meal"),
                            "name": m.get("name", "Meal"),
                            "calories": m.get("calories"),
                            "protein_g": m.get("protein_g"),
                        }
                        for m in meals
                    ],
                    "total_calories": day_data.get("total_calories"),
                    "total_protein": day_data.get("total_protein"),
                })

        return ToolResult(
            success=True,
            data={
                "meal_plan_id": meal_plan.id,
                "name": meal_plan.name,
                "days": len(plan_data),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "plan": plan_preview,  # Include plan data for UI preview
            },
        )


class GenerateGroceryListTool(BaseTool):
    """Generate a grocery list from a meal plan or manual selection."""

    name = "generate_grocery_list"
    description = """Generate a consolidated grocery list from a meal plan.
    Combines ingredients, groups by category, and calculates quantities.
    Use this when user asks for a shopping list or grocery list."""

    parameters = {
        "meal_plan_id": {
            "type": "string",
            "description": "ID of the meal plan to generate grocery list from",
            "optional": True,
        },
        "items": {
            "type": "array",
            "description": "Consolidated grocery items with name, quantity, unit, and category",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit": {"type": "string"},
                    "category": {"type": "string"},
                },
            },
        },
        "name": {
            "type": "string",
            "description": "Name for the grocery list",
            "optional": True,
        },
    }

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Create and store the grocery list."""
        items = kwargs.get("items", [])
        meal_plan_id = kwargs.get("meal_plan_id")
        name = kwargs.get("name", f"Grocery List - {datetime.now().strftime('%b %d')}")

        if not items:
            return ToolResult(
                success=False,
                error="No grocery items provided",
            )

        # Add checked=False to each item
        for item in items:
            item["checked"] = False

        grocery_list = GroceryList(
            user_id=self.user_id,
            meal_plan_id=meal_plan_id,
            name=name,
            items=items,
        )
        self.db.add(grocery_list)
        await self.db.commit()

        # Group items by category for display
        by_category = {}
        for item in items:
            cat = item.get("category", "other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item)

        return ToolResult(
            success=True,
            data={
                "grocery_list_id": grocery_list.id,
                "name": name,
                "total_items": len(items),
                "by_category": by_category,
            },
        )


class GetMealSuggestionTool(BaseTool):
    """Get a quick meal suggestion based on available ingredients or preferences."""

    name = "suggest_meal"
    description = """Suggest a specific meal based on context like:
    - Available ingredients the user mentions
    - Time of day
    - Dietary preferences
    - Remaining macro targets for the day
    Use this for quick meal ideas, not full meal planning."""

    parameters = {
        "meal_type": {
            "type": "string",
            "description": "Type of meal",
            "enum": ["breakfast", "lunch", "dinner", "snack"],
        },
        "name": {
            "type": "string",
            "description": "Name of the suggested meal",
        },
        "description": {
            "type": "string",
            "description": "Brief description of the meal",
        },
        "calories": {
            "type": "integer",
            "description": "Total calories",
        },
        "protein_g": {
            "type": "number",
            "description": "Protein in grams",
        },
        "carbs_g": {
            "type": "number",
            "description": "Carbohydrates in grams",
        },
        "fat_g": {
            "type": "number",
            "description": "Fat in grams",
        },
        "ingredients": {
            "type": "array",
            "description": "List of ingredients with name, quantity, unit",
            "items": {"type": "object"},
            "optional": True,
        },
        "prep_time_min": {
            "type": "integer",
            "description": "Preparation time in minutes",
            "optional": True,
        },
        "instructions": {
            "type": "string",
            "description": "Cooking instructions",
            "optional": True,
        },
        "why_recommended": {
            "type": "string",
            "description": "Brief explanation of why this meal fits the user's needs",
            "optional": True,
        },
    }

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Return the meal suggestion (doesn't persist - just for display)."""
        return ToolResult(
            success=True,
            data={
                "meal_type": kwargs.get("meal_type"),
                "name": kwargs.get("name"),
                "description": kwargs.get("description"),
                "calories": kwargs.get("calories"),
                "protein_g": kwargs.get("protein_g"),
                "carbs_g": kwargs.get("carbs_g"),
                "fat_g": kwargs.get("fat_g"),
                "ingredients": kwargs.get("ingredients", []),
                "prep_time_min": kwargs.get("prep_time_min"),
                "instructions": kwargs.get("instructions"),
                "why_recommended": kwargs.get("why_recommended"),
            },
        )
