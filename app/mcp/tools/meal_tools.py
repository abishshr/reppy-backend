"""Meal logging tools for MCP."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.infrastructure.database import MealLog
from app.infrastructure.redis import redis_client
from app.mcp.tools.base import BaseTool, ToolResult


class LogMealSuggestionTool(BaseTool):
    """
    Parse user's meal description and suggest a structured log.

    This tool is called when the user describes what they ate.
    It returns a suggestion that requires confirmation before being logged.
    """

    name = "log_meal_suggestion"
    description = """Parse the user's meal description and return a structured suggestion
    with estimated nutritional information including macros, micronutrients, vitamins, and minerals.
    The suggestion requires user confirmation before being saved.
    IMPORTANT: Always estimate ALL nutrients based on typical food values:
    - Macros: calories, protein, carbs, fat
    - Micronutrients: sugar, fiber, sodium, saturated_fat, cholesterol
    - Vitamins: A, C, D, E, K, B1, B2, B3, B6, B9, B12
    - Minerals: calcium, iron, magnesium, phosphorus, potassium, zinc, selenium, copper, manganese
    Include educational tips about the meal."""

    parameters = {
        "items": {
            "type": "array",
            "description": "List of food items with name, quantity, and unit",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Food item name"},
                    "quantity": {"type": "number", "description": "Amount"},
                    "unit": {"type": "string", "description": "Unit (grams, oz, cup, piece)"},
                },
            },
        },
        "estimated_calories": {
            "type": "integer",
            "description": "Estimated total calories",
        },
        "estimated_protein_g": {
            "type": "number",
            "description": "Estimated protein in grams",
        },
        "estimated_carbs_g": {
            "type": "number",
            "description": "Estimated carbohydrates in grams",
        },
        "estimated_fat_g": {
            "type": "number",
            "description": "Estimated fat in grams",
        },
        "estimated_sugar_g": {
            "type": "number",
            "description": "Estimated sugar in grams",
            "optional": True,
        },
        "estimated_fiber_g": {
            "type": "number",
            "description": "Estimated fiber in grams",
            "optional": True,
        },
        "estimated_sodium_mg": {
            "type": "number",
            "description": "Estimated sodium in milligrams",
            "optional": True,
        },
        "estimated_saturated_fat_g": {
            "type": "number",
            "description": "Estimated saturated fat in grams",
            "optional": True,
        },
        "estimated_cholesterol_mg": {
            "type": "number",
            "description": "Estimated cholesterol in milligrams",
            "optional": True,
        },
        # Vitamin estimates
        "estimated_vitamin_a_mcg": {
            "type": "number",
            "description": "Estimated Vitamin A in mcg (from carrots, sweet potatoes, eggs, dairy)",
            "optional": True,
        },
        "estimated_vitamin_c_mg": {
            "type": "number",
            "description": "Estimated Vitamin C in mg (from citrus, peppers, broccoli)",
            "optional": True,
        },
        "estimated_vitamin_d_mcg": {
            "type": "number",
            "description": "Estimated Vitamin D in mcg (from fatty fish, eggs, fortified foods)",
            "optional": True,
        },
        "estimated_vitamin_e_mg": {
            "type": "number",
            "description": "Estimated Vitamin E in mg (from nuts, seeds, oils)",
            "optional": True,
        },
        "estimated_vitamin_k_mcg": {
            "type": "number",
            "description": "Estimated Vitamin K in mcg (from leafy greens, broccoli)",
            "optional": True,
        },
        "estimated_vitamin_b1_mg": {
            "type": "number",
            "description": "Estimated Thiamin B1 in mg (from grains, pork, legumes)",
            "optional": True,
        },
        "estimated_vitamin_b2_mg": {
            "type": "number",
            "description": "Estimated Riboflavin B2 in mg (from dairy, eggs, meats)",
            "optional": True,
        },
        "estimated_vitamin_b3_mg": {
            "type": "number",
            "description": "Estimated Niacin B3 in mg (from chicken, tuna, peanuts)",
            "optional": True,
        },
        "estimated_vitamin_b6_mg": {
            "type": "number",
            "description": "Estimated Vitamin B6 in mg (from chicken, fish, potatoes)",
            "optional": True,
        },
        "estimated_vitamin_b9_mcg": {
            "type": "number",
            "description": "Estimated Folate B9 in mcg (from leafy greens, legumes)",
            "optional": True,
        },
        "estimated_vitamin_b12_mcg": {
            "type": "number",
            "description": "Estimated Vitamin B12 in mcg (from meat, fish, dairy, eggs)",
            "optional": True,
        },
        # Mineral estimates
        "estimated_calcium_mg": {
            "type": "number",
            "description": "Estimated Calcium in mg (from dairy, leafy greens, tofu)",
            "optional": True,
        },
        "estimated_iron_mg": {
            "type": "number",
            "description": "Estimated Iron in mg (from red meat, spinach, lentils)",
            "optional": True,
        },
        "estimated_magnesium_mg": {
            "type": "number",
            "description": "Estimated Magnesium in mg (from nuts, seeds, whole grains)",
            "optional": True,
        },
        "estimated_phosphorus_mg": {
            "type": "number",
            "description": "Estimated Phosphorus in mg (from dairy, meat, fish)",
            "optional": True,
        },
        "estimated_potassium_mg": {
            "type": "number",
            "description": "Estimated Potassium in mg (from bananas, potatoes, beans)",
            "optional": True,
        },
        "estimated_zinc_mg": {
            "type": "number",
            "description": "Estimated Zinc in mg (from oysters, beef, pumpkin seeds)",
            "optional": True,
        },
        "estimated_selenium_mcg": {
            "type": "number",
            "description": "Estimated Selenium in mcg (from brazil nuts, fish, eggs)",
            "optional": True,
        },
        "estimated_copper_mcg": {
            "type": "number",
            "description": "Estimated Copper in mcg (from shellfish, nuts, seeds)",
            "optional": True,
        },
        "estimated_manganese_mg": {
            "type": "number",
            "description": "Estimated Manganese in mg (from whole grains, nuts, tea)",
            "optional": True,
        },
        "confidence": {
            "type": "number",
            "description": "Confidence score 0.0-1.0",
        },
        "notes": {
            "type": "string",
            "description": "Educational tips or notes about the meal",
            "optional": True,
        },
        "meal_type": {
            "type": "string",
            "description": "Type of meal (breakfast, lunch, dinner, snack)",
            "optional": True,
        },
        "clarifying_questions": {
            "type": "array",
            "description": "Questions to ask if information is missing",
            "items": {"type": "string"},
            "optional": True,
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Create a meal suggestion and store it pending confirmation."""
        suggestion_id = str(uuid4())

        # Store the suggestion in Redis for later confirmation
        suggestion_data = {
            "user_id": self.user_id,
            "suggestion_id": suggestion_id,
            "items": kwargs.get("items", []),
            "calories": kwargs.get("estimated_calories", 0),
            "protein_g": kwargs.get("estimated_protein_g", 0),
            "carbs_g": kwargs.get("estimated_carbs_g", 0),
            "fat_g": kwargs.get("estimated_fat_g", 0),
            # Micronutrients
            "sugar_g": kwargs.get("estimated_sugar_g", 0),
            "fiber_g": kwargs.get("estimated_fiber_g", 0),
            "sodium_mg": kwargs.get("estimated_sodium_mg", 0),
            "saturated_fat_g": kwargs.get("estimated_saturated_fat_g", 0),
            "cholesterol_mg": kwargs.get("estimated_cholesterol_mg"),
            # Vitamins
            "vitamin_a_mcg": kwargs.get("estimated_vitamin_a_mcg"),
            "vitamin_c_mg": kwargs.get("estimated_vitamin_c_mg"),
            "vitamin_d_mcg": kwargs.get("estimated_vitamin_d_mcg"),
            "vitamin_e_mg": kwargs.get("estimated_vitamin_e_mg"),
            "vitamin_k_mcg": kwargs.get("estimated_vitamin_k_mcg"),
            "vitamin_b1_mg": kwargs.get("estimated_vitamin_b1_mg"),
            "vitamin_b2_mg": kwargs.get("estimated_vitamin_b2_mg"),
            "vitamin_b3_mg": kwargs.get("estimated_vitamin_b3_mg"),
            "vitamin_b6_mg": kwargs.get("estimated_vitamin_b6_mg"),
            "vitamin_b9_mcg": kwargs.get("estimated_vitamin_b9_mcg"),
            "vitamin_b12_mcg": kwargs.get("estimated_vitamin_b12_mcg"),
            # Minerals
            "calcium_mg": kwargs.get("estimated_calcium_mg"),
            "iron_mg": kwargs.get("estimated_iron_mg"),
            "magnesium_mg": kwargs.get("estimated_magnesium_mg"),
            "phosphorus_mg": kwargs.get("estimated_phosphorus_mg"),
            "potassium_mg": kwargs.get("estimated_potassium_mg"),
            "zinc_mg": kwargs.get("estimated_zinc_mg"),
            "selenium_mcg": kwargs.get("estimated_selenium_mcg"),
            "copper_mcg": kwargs.get("estimated_copper_mcg"),
            "manganese_mg": kwargs.get("estimated_manganese_mg"),
            "confidence": kwargs.get("confidence", 0.5),
            "notes": kwargs.get("notes"),
            "meal_type": kwargs.get("meal_type"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Store in Redis with 1-hour expiration
        await redis_client.set(
            f"meal_suggestion:{suggestion_id}",
            suggestion_data,
            expire_seconds=3600,
        )

        return ToolResult(
            success=True,
            data={
                "suggestion_id": suggestion_id,
                **suggestion_data,
                "clarifying_questions": kwargs.get("clarifying_questions", []),
            },
            requires_confirmation=True,
            suggestion_id=suggestion_id,
        )


class ConfirmMealLogTool(BaseTool):
    """Confirm and save a meal suggestion to the database."""

    name = "confirm_log_meal"
    description = """Confirm a pending meal suggestion and save it to the database.
    Only call this after the user has confirmed the meal suggestion."""

    parameters = {
        "suggestion_id": {
            "type": "string",
            "description": "The ID of the pending meal suggestion to confirm",
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Confirm and save the meal to the database."""
        suggestion_id = kwargs.get("suggestion_id")

        if not suggestion_id:
            return ToolResult(
                success=False,
                error="suggestion_id is required",
            )

        # Retrieve the suggestion from Redis
        suggestion = await redis_client.get(f"meal_suggestion:{suggestion_id}")

        if not suggestion:
            return ToolResult(
                success=False,
                error="Suggestion not found or expired. Please create a new meal log.",
            )

        # Verify user owns this suggestion
        if suggestion.get("user_id") != self.user_id:
            return ToolResult(
                success=False,
                error="Unauthorized to confirm this suggestion",
            )

        # Create the meal log
        meal = MealLog(
            user_id=self.user_id,
            logged_at=datetime.now(timezone.utc),
            meal_type=suggestion.get("meal_type"),
            items=suggestion.get("items", []),
            calories=suggestion.get("calories"),
            protein_g=suggestion.get("protein_g"),
            carbs_g=suggestion.get("carbs_g"),
            fat_g=suggestion.get("fat_g"),
            # Micronutrients
            sugar_g_est=suggestion.get("sugar_g"),
            fiber_g_est=suggestion.get("fiber_g"),
            sodium_mg_est=suggestion.get("sodium_mg"),
            saturated_fat_g_est=suggestion.get("saturated_fat_g"),
            cholesterol_mg_est=suggestion.get("cholesterol_mg"),
            # Vitamins
            vitamin_a_mcg_est=suggestion.get("vitamin_a_mcg"),
            vitamin_c_mg_est=suggestion.get("vitamin_c_mg"),
            vitamin_d_mcg_est=suggestion.get("vitamin_d_mcg"),
            vitamin_e_mg_est=suggestion.get("vitamin_e_mg"),
            vitamin_k_mcg_est=suggestion.get("vitamin_k_mcg"),
            vitamin_b1_mg_est=suggestion.get("vitamin_b1_mg"),
            vitamin_b2_mg_est=suggestion.get("vitamin_b2_mg"),
            vitamin_b3_mg_est=suggestion.get("vitamin_b3_mg"),
            vitamin_b6_mg_est=suggestion.get("vitamin_b6_mg"),
            vitamin_b9_mcg_est=suggestion.get("vitamin_b9_mcg"),
            vitamin_b12_mcg_est=suggestion.get("vitamin_b12_mcg"),
            # Minerals
            calcium_mg_est=suggestion.get("calcium_mg"),
            iron_mg_est=suggestion.get("iron_mg"),
            magnesium_mg_est=suggestion.get("magnesium_mg"),
            phosphorus_mg_est=suggestion.get("phosphorus_mg"),
            potassium_mg_est=suggestion.get("potassium_mg"),
            zinc_mg_est=suggestion.get("zinc_mg"),
            selenium_mcg_est=suggestion.get("selenium_mcg"),
            copper_mcg_est=suggestion.get("copper_mcg"),
            manganese_mg_est=suggestion.get("manganese_mg"),
            confidence=suggestion.get("confidence"),
            notes=suggestion.get("notes"),
        )

        self.db.add(meal)
        await self.db.flush()

        # Delete the suggestion from Redis
        await redis_client.delete(f"meal_suggestion:{suggestion_id}")

        return ToolResult(
            success=True,
            data={
                "meal_id": meal.id,
                "message": "Meal logged successfully",
                "calories": meal.calories,
                "protein_g": meal.protein_g,
                "carbs_g": meal.carbs_g,
                "fat_g": meal.fat_g,
            },
        )
