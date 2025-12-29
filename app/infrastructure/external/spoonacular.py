"""Spoonacular API client for recipe images and data."""

import httpx
from typing import Optional

from app.config import settings


class SpoonacularClient:
    """Client for Spoonacular API (RapidAPI)."""

    BASE_URL = "https://spoonacular-recipe-food-nutrition-v1.p.rapidapi.com"

    def __init__(self):
        self.api_key = settings.spoonacular_api_key
        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "spoonacular-recipe-food-nutrition-v1.p.rapidapi.com",
        }
        self._cache: dict[str, dict] = {}

    async def search_recipe(self, query: str, diet: str = None) -> Optional[dict]:
        """
        Search for a recipe by name and return its details including image URL.

        Returns dict with: id, title, image, readyInMinutes, servings, nutrition
        """
        if not self.api_key:
            return None

        # Clean up query for better matching - extract main food item
        clean_query = self._clean_query(query)

        # Check cache first
        cache_key = f"{clean_query.lower().strip()}:{diet or ''}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            async with httpx.AsyncClient() as client:
                # Search for recipes with better parameters
                params = {
                    "query": clean_query,
                    "number": 3,  # Get top 3 to find best match
                    "addRecipeNutrition": "true",
                    "addRecipeInstructions": "false",  # We'll use AI for instructions
                    "sort": "popularity",  # Get most popular (usually best images)
                    "sortDirection": "desc",
                }
                if diet:
                    params["diet"] = diet

                response = await client.get(
                    f"{self.BASE_URL}/recipes/complexSearch",
                    headers=self.headers,
                    params=params,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    if results and len(results) > 0:
                        # Pick the best result (first one with an image)
                        recipe = None
                        for r in results:
                            if r.get("image"):
                                recipe = r
                                break
                        if not recipe:
                            recipe = results[0]

                        nutrition = recipe.get("nutrition", {})
                        nutrients = {n["name"]: n["amount"] for n in nutrition.get("nutrients", [])}

                        result = {
                            "id": recipe.get("id"),
                            "title": recipe.get("title"),
                            "image": recipe.get("image"),
                            "ready_in_minutes": recipe.get("readyInMinutes"),
                            "servings": recipe.get("servings"),
                            "calories": nutrients.get("Calories"),
                            "protein": nutrients.get("Protein"),
                            "carbs": nutrients.get("Carbohydrates"),
                            "fat": nutrients.get("Fat"),
                        }
                        self._cache[cache_key] = result
                        return result

        except Exception as e:
            print(f"Spoonacular API error: {e}")

        return None

    def _clean_query(self, query: str) -> str:
        """Clean up meal name for better recipe search results."""
        # Remove common prefixes/suffixes that hurt search
        query = query.lower()

        # Remove descriptive words that don't help search
        remove_words = [
            "with", "and", "&", "topped", "served", "fresh", "homemade",
            "delicious", "healthy", "simple", "easy", "quick",
            "for", "the", "a", "an"
        ]

        words = query.split()
        cleaned = [w for w in words if w not in remove_words]

        # If we removed too much, use original
        if len(cleaned) < 2:
            return query

        return " ".join(cleaned)

    async def get_recipe_image(self, query: str) -> Optional[str]:
        """Get just the image URL for a recipe/meal."""
        recipe = await self.search_recipe(query)
        return recipe.get("image") if recipe else None

    async def enrich_meals(self, meals: list[dict], diet: str = None) -> list[dict]:
        """
        Enrich a list of meals with images from Spoonacular.

        Takes meals with 'name' field and adds 'image_url'.
        """
        enriched = []
        for meal in meals:
            name = meal.get("name", "")
            if name and not meal.get("image_url"):
                try:
                    recipe = await self.search_recipe(name, diet)
                    if recipe:
                        meal["image_url"] = recipe.get("image")
                        meal["ready_in_minutes"] = recipe.get("ready_in_minutes")
                        meal["servings"] = recipe.get("servings")
                except Exception as e:
                    print(f"Failed to enrich meal {name}: {e}")
            enriched.append(meal)
        return enriched


# Singleton instance
_client: Optional[SpoonacularClient] = None


def get_spoonacular_client() -> SpoonacularClient:
    """Get the Spoonacular client singleton."""
    global _client
    if _client is None:
        _client = SpoonacularClient()
    return _client
