"""USDA FoodData Central API client for food database lookups."""

import httpx
from typing import Optional
from pydantic import BaseModel

from app.config import settings


class USDAFood(BaseModel):
    """Food data from USDA FoodData Central."""

    fdc_id: int  # USDA Food Data Central ID
    name: str
    brand: Optional[str] = None
    description: Optional[str] = None
    gtin_upc: Optional[str] = None  # Barcode

    # Data type: Foundation, SR Legacy, Branded, Survey
    data_type: Optional[str] = None

    # Serving info
    serving_size: Optional[float] = None
    serving_size_unit: Optional[str] = None
    household_serving: Optional[str] = None  # "1 cup", "1 medium", etc.

    # Nutrition per 100g
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    saturated_fat_g: Optional[float] = None
    cholesterol_mg: Optional[float] = None


class USDAClient:
    """Client for USDA FoodData Central API."""

    BASE_URL = "https://api.nal.usda.gov/fdc/v1"

    def __init__(self):
        self.api_key = settings.usda_api_key
        self._cache: dict[str, USDAFood] = {}

    async def search_foods(
        self,
        query: str,
        limit: int = 20,
        data_types: Optional[list[str]] = None
    ) -> list[USDAFood]:
        """
        Search for foods by name.

        Args:
            query: Search query
            limit: Maximum results to return
            data_types: Filter by data type (Foundation, Branded, SR Legacy, Survey)

        Returns:
            List of matching foods
        """
        if not self.api_key:
            return []

        try:
            async with httpx.AsyncClient() as client:
                # Use the search endpoint
                body = {
                    "query": query,
                    "pageSize": limit,
                    "sortBy": "dataType.keyword",
                    "sortOrder": "asc",
                }

                if data_types:
                    body["dataType"] = data_types
                else:
                    # Default: prefer branded (has barcodes) and foundation (accurate)
                    body["dataType"] = ["Branded", "Foundation", "SR Legacy"]

                response = await client.post(
                    f"{self.BASE_URL}/foods/search",
                    params={"api_key": self.api_key},
                    json=body,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    foods = []
                    for item in data.get("foods", []):
                        food = self._parse_food(item)
                        if food:
                            foods.append(food)
                    return foods

        except Exception as e:
            print(f"USDA API search error: {e}")

        return []

    async def get_food_by_id(self, fdc_id: int) -> Optional[USDAFood]:
        """
        Get detailed food information by FDC ID.

        Args:
            fdc_id: USDA FoodData Central ID

        Returns:
            USDAFood if found, None otherwise
        """
        if not self.api_key:
            return None

        cache_key = f"fdc_{fdc_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/food/{fdc_id}",
                    params={"api_key": self.api_key},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    food = self._parse_food_detail(data)
                    if food:
                        self._cache[cache_key] = food
                        return food

        except Exception as e:
            print(f"USDA API get food error: {e}")

        return None

    async def search_by_barcode(self, barcode: str) -> Optional[USDAFood]:
        """
        Search for a food by barcode (GTIN/UPC).

        Args:
            barcode: The product barcode

        Returns:
            USDAFood if found, None otherwise
        """
        if not self.api_key:
            return None

        cache_key = f"barcode_{barcode}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            async with httpx.AsyncClient() as client:
                # Search branded foods by GTIN/UPC
                body = {
                    "query": barcode,
                    "dataType": ["Branded"],
                    "pageSize": 5,
                }

                response = await client.post(
                    f"{self.BASE_URL}/foods/search",
                    params={"api_key": self.api_key},
                    json=body,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    foods = data.get("foods", [])

                    # Find exact barcode match
                    for item in foods:
                        if item.get("gtinUpc") == barcode:
                            food = self._parse_food(item)
                            if food:
                                self._cache[cache_key] = food
                                return food

                    # If no exact match, try first result
                    if foods:
                        food = self._parse_food(foods[0])
                        if food:
                            self._cache[cache_key] = food
                            return food

        except Exception as e:
            print(f"USDA API barcode search error: {e}")

        return None

    def _parse_food(self, data: dict) -> Optional[USDAFood]:
        """Parse search result into USDAFood."""
        try:
            fdc_id = data.get("fdcId")
            description = data.get("description", "")

            if not fdc_id or not description:
                return None

            # Get brand for branded foods
            brand = data.get("brandOwner") or data.get("brandName")

            # Parse nutrients
            nutrients = {}
            for nutrient in data.get("foodNutrients", []):
                nutrient_name = nutrient.get("nutrientName", "")
                value = nutrient.get("value")
                if value is not None:
                    nutrients[nutrient_name] = value

            return USDAFood(
                fdc_id=fdc_id,
                name=description,
                brand=brand,
                description=data.get("additionalDescriptions"),
                gtin_upc=data.get("gtinUpc"),
                data_type=data.get("dataType"),
                serving_size=data.get("servingSize"),
                serving_size_unit=data.get("servingSizeUnit"),
                household_serving=data.get("householdServingFullText"),
                calories=nutrients.get("Energy"),
                protein_g=nutrients.get("Protein"),
                carbs_g=nutrients.get("Carbohydrate, by difference"),
                fat_g=nutrients.get("Total lipid (fat)"),
                fiber_g=nutrients.get("Fiber, total dietary"),
                sugar_g=nutrients.get("Sugars, total including NLEA")
                or nutrients.get("Total Sugars"),
                sodium_mg=nutrients.get("Sodium, Na"),
                saturated_fat_g=nutrients.get("Fatty acids, total saturated"),
                cholesterol_mg=nutrients.get("Cholesterol"),
            )

        except Exception as e:
            print(f"Error parsing USDA food: {e}")
            return None

    def _parse_food_detail(self, data: dict) -> Optional[USDAFood]:
        """Parse detailed food response into USDAFood."""
        try:
            fdc_id = data.get("fdcId")
            description = data.get("description", "")

            if not fdc_id or not description:
                return None

            # Get brand for branded foods
            brand = data.get("brandOwner") or data.get("brandName")

            # Parse nutrients from detailed response
            nutrients = {}
            for nutrient in data.get("foodNutrients", []):
                nutrient_info = nutrient.get("nutrient", {})
                nutrient_name = nutrient_info.get("name", "")
                value = nutrient.get("amount")
                if value is not None:
                    nutrients[nutrient_name] = value

            # Get serving info
            portions = data.get("foodPortions", [])
            household_serving = None
            serving_size = None
            serving_size_unit = None

            if portions:
                portion = portions[0]
                household_serving = portion.get("portionDescription")
                serving_size = portion.get("gramWeight")
                serving_size_unit = "g"

            return USDAFood(
                fdc_id=fdc_id,
                name=description,
                brand=brand,
                description=data.get("additionalDescriptions"),
                gtin_upc=data.get("gtinUpc"),
                data_type=data.get("dataType"),
                serving_size=serving_size or data.get("servingSize"),
                serving_size_unit=serving_size_unit or data.get("servingSizeUnit"),
                household_serving=household_serving
                or data.get("householdServingFullText"),
                calories=nutrients.get("Energy"),
                protein_g=nutrients.get("Protein"),
                carbs_g=nutrients.get("Carbohydrate, by difference"),
                fat_g=nutrients.get("Total lipid (fat)"),
                fiber_g=nutrients.get("Fiber, total dietary"),
                sugar_g=nutrients.get("Sugars, total including NLEA")
                or nutrients.get("Total Sugars"),
                sodium_mg=nutrients.get("Sodium, Na"),
                saturated_fat_g=nutrients.get("Fatty acids, total saturated"),
                cholesterol_mg=nutrients.get("Cholesterol"),
            )

        except Exception as e:
            print(f"Error parsing USDA food detail: {e}")
            return None


# Singleton instance
_client: Optional[USDAClient] = None


def get_usda_client() -> USDAClient:
    """Get the USDA client singleton."""
    global _client
    if _client is None:
        _client = USDAClient()
    return _client
