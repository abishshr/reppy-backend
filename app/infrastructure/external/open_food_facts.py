"""Open Food Facts API client for food database lookups."""

import httpx
from typing import Optional
from pydantic import BaseModel


class OpenFoodFactsProduct(BaseModel):
    """Product data from Open Food Facts."""

    code: str  # Barcode
    name: str
    brand: Optional[str] = None
    image_url: Optional[str] = None
    image_thumb_url: Optional[str] = None

    # Serving info
    serving_size: Optional[str] = None
    serving_size_g: Optional[float] = None

    # Nutrition per 100g (we'll convert to per serving)
    calories_100g: Optional[float] = None
    protein_100g: Optional[float] = None
    carbs_100g: Optional[float] = None
    fat_100g: Optional[float] = None
    fiber_100g: Optional[float] = None
    sugar_100g: Optional[float] = None
    sodium_100g: Optional[float] = None
    saturated_fat_100g: Optional[float] = None

    # Per serving (if available)
    calories_serving: Optional[float] = None
    protein_serving: Optional[float] = None
    carbs_serving: Optional[float] = None
    fat_serving: Optional[float] = None


class OpenFoodFactsClient:
    """Client for Open Food Facts API (free, no API key required)."""

    BASE_URL = "https://world.openfoodfacts.org/api/v2"
    SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"

    def __init__(self):
        self._cache: dict[str, OpenFoodFactsProduct] = {}

    async def get_product_by_barcode(self, barcode: str) -> Optional[OpenFoodFactsProduct]:
        """
        Lookup a product by barcode.

        Args:
            barcode: The product barcode (EAN-13, UPC-A, etc.)

        Returns:
            OpenFoodFactsProduct if found, None otherwise
        """
        # Check cache
        if barcode in self._cache:
            return self._cache[barcode]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/product/{barcode}.json",
                    timeout=10.0,
                    headers={
                        "User-Agent": "Reppy/1.0 (iOS fitness app)"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == 1 and data.get("product"):
                        product = self._parse_product(data["product"], barcode)
                        if product:
                            self._cache[barcode] = product
                            return product

        except Exception as e:
            print(f"Open Food Facts API error: {e}")

        return None

    async def search_products(
        self,
        query: str,
        limit: int = 20,
        country: str = "us"
    ) -> list[OpenFoodFactsProduct]:
        """
        Search for products by name.

        Args:
            query: Search query
            limit: Maximum results to return
            country: Country code for localized results

        Returns:
            List of matching products
        """
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "search_terms": query,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": limit,
                    "countries_tags_en": country,
                    "sort_by": "popularity_key",  # Most popular first
                }

                response = await client.get(
                    self.SEARCH_URL,
                    params=params,
                    timeout=10.0,
                    headers={
                        "User-Agent": "Reppy/1.0 (iOS fitness app)"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    products = []
                    for item in data.get("products", []):
                        product = self._parse_product(item, item.get("code", ""))
                        if product and product.name:
                            products.append(product)
                    return products

        except Exception as e:
            print(f"Open Food Facts search error: {e}")

        return []

    def _parse_product(self, data: dict, barcode: str) -> Optional[OpenFoodFactsProduct]:
        """Parse raw API response into OpenFoodFactsProduct."""
        try:
            # Get product name
            name = (
                data.get("product_name_en")
                or data.get("product_name")
                or data.get("generic_name_en")
                or data.get("generic_name")
            )

            if not name:
                return None

            # Get brand
            brand = data.get("brands", "").split(",")[0].strip() if data.get("brands") else None

            # Get images
            image_url = data.get("image_front_url") or data.get("image_url")
            image_thumb = data.get("image_front_thumb_url") or data.get("image_thumb_url")

            # Get serving info
            serving_size = data.get("serving_size")
            serving_quantity = data.get("serving_quantity")

            # Try to parse serving size in grams
            serving_size_g = None
            if serving_quantity:
                try:
                    serving_size_g = float(serving_quantity)
                except (ValueError, TypeError):
                    pass

            # Get nutriments
            nutriments = data.get("nutriments", {})

            # Nutrition per 100g
            calories_100g = nutriments.get("energy-kcal_100g")
            if calories_100g is None:
                # Try to convert from kJ
                energy_kj = nutriments.get("energy_100g")
                if energy_kj:
                    calories_100g = energy_kj / 4.184

            protein_100g = nutriments.get("proteins_100g")
            carbs_100g = nutriments.get("carbohydrates_100g")
            fat_100g = nutriments.get("fat_100g")
            fiber_100g = nutriments.get("fiber_100g")
            sugar_100g = nutriments.get("sugars_100g")
            sodium_100g = nutriments.get("sodium_100g")
            saturated_fat_100g = nutriments.get("saturated-fat_100g")

            # Nutrition per serving (if available)
            calories_serving = nutriments.get("energy-kcal_serving")
            protein_serving = nutriments.get("proteins_serving")
            carbs_serving = nutriments.get("carbohydrates_serving")
            fat_serving = nutriments.get("fat_serving")

            return OpenFoodFactsProduct(
                code=barcode,
                name=name,
                brand=brand,
                image_url=image_url,
                image_thumb_url=image_thumb,
                serving_size=serving_size,
                serving_size_g=serving_size_g,
                calories_100g=calories_100g,
                protein_100g=protein_100g,
                carbs_100g=carbs_100g,
                fat_100g=fat_100g,
                fiber_100g=fiber_100g,
                sugar_100g=sugar_100g,
                sodium_100g=sodium_100g,
                saturated_fat_100g=saturated_fat_100g,
                calories_serving=calories_serving,
                protein_serving=protein_serving,
                carbs_serving=carbs_serving,
                fat_serving=fat_serving,
            )

        except Exception as e:
            print(f"Error parsing Open Food Facts product: {e}")
            return None


# Singleton instance
_client: Optional[OpenFoodFactsClient] = None


def get_open_food_facts_client() -> OpenFoodFactsClient:
    """Get the Open Food Facts client singleton."""
    global _client
    if _client is None:
        _client = OpenFoodFactsClient()
    return _client
