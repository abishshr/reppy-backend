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
    with estimated nutritional information including macros AND micronutrients.
    The suggestion requires user confirmation before being saved.
    IMPORTANT: Always estimate and include sugar_g, fiber_g, sodium_mg, and saturated_fat_g based on typical food values.
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
            "description": "Estimated sugar in grams (REQUIRED - estimate based on typical values)",
        },
        "estimated_fiber_g": {
            "type": "number",
            "description": "Estimated fiber in grams (REQUIRED - estimate based on typical values)",
        },
        "estimated_sodium_mg": {
            "type": "number",
            "description": "Estimated sodium in milligrams (REQUIRED - estimate based on typical values)",
        },
        "estimated_saturated_fat_g": {
            "type": "number",
            "description": "Estimated saturated fat in grams (REQUIRED - estimate based on typical values)",
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
            sugar_g_est=suggestion.get("sugar_g_est"),
            fiber_g_est=suggestion.get("fiber_g_est"),
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
