"""Meal recommendation tools for MCP."""

from typing import Any

from app.mcp.tools.base import BaseTool, ToolResult


class MenuRecommendationsTool(BaseTool):
    """
    Analyze a restaurant menu and provide personalized recommendations.

    This tool is called when the user shares a menu (text or photo) and wants
    recommendations on what to order based on their profile, goals, and remaining macros.
    """

    name = "menu_recommendations"
    description = """Analyze a restaurant or food menu and provide personalized recommendations.
    Use this when the user shares a menu (text, list of items, or describes options) and asks
    what they should order. Consider their dietary preferences, allergies, fitness goals,
    and remaining daily macros to suggest the best options."""

    parameters = {
        "menu_items": {
            "type": "array",
            "description": "List of menu items identified from the menu with estimated nutrition",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Item name"},
                    "description": {"type": "string", "description": "Item description"},
                    "estimated_calories": {"type": "integer", "description": "Estimated calories"},
                    "estimated_protein_g": {"type": "number", "description": "Estimated protein"},
                    "estimated_carbs_g": {"type": "number", "description": "Estimated carbs"},
                    "estimated_fat_g": {"type": "number", "description": "Estimated fat"},
                },
            },
        },
        "best_choices": {
            "type": "array",
            "description": "Top 2-3 recommended items that best fit user's goals and remaining macros",
            "items": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "Name of the menu item"},
                    "reason": {"type": "string", "description": "Why this is a good choice"},
                    "modifications": {
                        "type": "array",
                        "description": "Suggested modifications",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "ok_choices": {
            "type": "array",
            "description": "Acceptable options that could work with modifications",
            "items": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "Name of the menu item"},
                    "reason": {"type": "string", "description": "Why this is an OK choice"},
                    "modifications": {
                        "type": "array",
                        "description": "Modifications needed",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "avoid": {
            "type": "array",
            "description": "Items to avoid based on goals, allergies, or dietary restrictions",
            "items": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "Name of the menu item"},
                    "reason": {"type": "string", "description": "Why to avoid this item"},
                },
            },
        },
        "allergy_warnings": {
            "type": "array",
            "description": "Items that may contain user allergens (empty array if none)",
            "items": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "Name of the menu item"},
                    "allergen": {"type": "string", "description": "The allergen concern"},
                    "note": {"type": "string", "description": "Additional safety note"},
                },
            },
        },
        "overall_advice": {
            "type": "string",
            "description": "Brief overall advice for ordering at this restaurant",
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Return the menu recommendations."""
        best_choices = kwargs.get("best_choices", [])
        ok_choices = kwargs.get("ok_choices", [])
        avoid = kwargs.get("avoid", [])
        allergy_warnings = kwargs.get("allergy_warnings", [])
        menu_items = kwargs.get("menu_items", [])
        overall_advice = kwargs.get("overall_advice", "")

        if not best_choices and not ok_choices:
            return ToolResult(
                success=False,
                error="Could not generate menu recommendations. Please provide more menu details.",
            )

        return ToolResult(
            success=True,
            data={
                "menu_items_analyzed": len(menu_items),
                "best_choices": best_choices,
                "ok_choices": ok_choices,
                "avoid": avoid,
                "allergy_warnings": allergy_warnings,
                "overall_advice": overall_advice,
            },
        )


class SuggestMealsTool(BaseTool):
    """
    Suggest personalized meal ideas based on user's profile and remaining macros.

    This tool is called when the user asks for meal suggestions or recommendations.
    It provides meal ideas that fit their dietary preferences and remaining daily targets.
    """

    name = "suggest_meals"
    description = """Suggest personalized meal ideas based on the user's profile, dietary
    preferences, and remaining daily macro targets. Use this when the user asks for meal
    suggestions, recommendations, or ideas for what to eat."""

    parameters = {
        "meal_type": {
            "type": "string",
            "description": "Type of meal to suggest (breakfast, lunch, dinner, snack)",
            "optional": True,
        },
        "suggestions": {
            "type": "array",
            "description": "List of 3-5 meal suggestions with estimated nutrition",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Meal name/title"},
                    "description": {"type": "string", "description": "Brief description"},
                    "ingredients": {
                        "type": "array",
                        "description": "Main ingredients",
                        "items": {"type": "string"},
                    },
                    "estimated_calories": {"type": "integer", "description": "Estimated calories"},
                    "estimated_protein_g": {"type": "number", "description": "Estimated protein"},
                    "estimated_carbs_g": {"type": "number", "description": "Estimated carbs"},
                    "estimated_fat_g": {"type": "number", "description": "Estimated fat"},
                    "prep_time_min": {"type": "integer", "description": "Prep time in minutes"},
                    "matches_goals": {
                        "type": "boolean",
                        "description": "Whether this meal aligns with user's goals",
                    },
                },
            },
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of why these meals were suggested based on user's profile",
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Return the meal suggestions."""
        suggestions = kwargs.get("suggestions", [])
        meal_type = kwargs.get("meal_type")
        reasoning = kwargs.get("reasoning", "")

        if not suggestions:
            return ToolResult(
                success=False,
                error="No meal suggestions provided",
            )

        return ToolResult(
            success=True,
            data={
                "meal_type": meal_type,
                "suggestions": suggestions,
                "reasoning": reasoning,
                "count": len(suggestions),
            },
        )
