"""Unsplash API client for high-quality food images."""

import httpx
from typing import Optional

from app.config import settings


class UnsplashClient:
    """Client for Unsplash API - high-quality restaurant-style food images.

    Unsplash provides free, high-quality images suitable for
    displaying meals in an "Uber Eats"-like aesthetic.
    """

    BASE_URL = "https://api.unsplash.com"

    def __init__(self):
        self.access_key = settings.unsplash_access_key
        self._cache: dict[str, dict] = {}

    def _get_headers(self) -> dict:
        """Get request headers with API key."""
        return {
            "Authorization": f"Client-ID {self.access_key}",
            "Accept": "application/json",
        }

    async def search_food_image(
        self,
        food_name: str,
        style: str = "plated meal restaurant"
    ) -> Optional[dict]:
        """
        Search for a high-quality food image by meal name.

        Args:
            food_name: Name of the food/meal
            style: Additional style keywords (default: "plated meal restaurant")

        Returns dict with: id, url_regular, url_small, url_thumb, photographer, photographer_url
        """
        if not self.access_key:
            return None

        # Check cache first
        cache_key = f"{food_name.lower().strip()}:{style}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # Build search query for restaurant-style food
            query = f"{food_name} {style}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/search/photos",
                    headers=self._get_headers(),
                    params={
                        "query": query,
                        "per_page": 1,
                        "orientation": "landscape",
                        "content_filter": "high",  # Safe for all audiences
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])

                    if results:
                        photo = results[0]
                        urls = photo.get("urls", {})
                        user = photo.get("user", {})

                        result = {
                            "id": photo.get("id"),
                            "url_regular": urls.get("regular"),  # 1080px wide
                            "url_small": urls.get("small"),  # 400px wide
                            "url_thumb": urls.get("thumb"),  # 200px wide
                            "url_raw": urls.get("raw"),  # Original
                            "alt_description": photo.get("alt_description"),
                            "photographer": user.get("name"),
                            "photographer_url": user.get("links", {}).get("html"),
                            "source": "unsplash",
                        }
                        self._cache[cache_key] = result
                        return result

                elif response.status_code == 401:
                    print("Unsplash API: Invalid access key")
                elif response.status_code == 403:
                    print("Unsplash API: Rate limit exceeded")

        except httpx.TimeoutException:
            print(f"Unsplash API timeout for: {food_name}")
        except Exception as e:
            print(f"Unsplash API error: {e}")

        return None

    async def get_random_food_image(
        self,
        food_category: str = "healthy food"
    ) -> Optional[dict]:
        """
        Get a random food image for a category.

        Args:
            food_category: Category like "breakfast", "salad", "healthy food"

        Returns dict with image URLs
        """
        if not self.access_key:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/photos/random",
                    headers=self._get_headers(),
                    params={
                        "query": f"{food_category} plated",
                        "orientation": "landscape",
                        "content_filter": "high",
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    photo = response.json()
                    urls = photo.get("urls", {})
                    user = photo.get("user", {})

                    return {
                        "id": photo.get("id"),
                        "url_regular": urls.get("regular"),
                        "url_small": urls.get("small"),
                        "url_thumb": urls.get("thumb"),
                        "photographer": user.get("name"),
                        "source": "unsplash",
                    }

        except Exception as e:
            print(f"Unsplash API error: {e}")

        return None

    async def enrich_meals_with_images(
        self,
        meals: list[dict],
        prefer_unsplash: bool = True
    ) -> list[dict]:
        """
        Enrich a list of meals with high-quality Unsplash images.

        Takes meals with 'name' field and adds/updates 'image_url' and 'image_source'.
        Only updates if prefer_unsplash is True or no existing image.
        """
        enriched = []
        for meal in meals:
            name = meal.get("name", "")
            existing_image = meal.get("image_url")

            # Skip if already has image and we don't prefer Unsplash
            if existing_image and not prefer_unsplash:
                enriched.append(meal)
                continue

            if name:
                # Search for a food image matching the meal name
                unsplash_image = await self.search_food_image(name)
                if unsplash_image and unsplash_image.get("url_regular"):
                    meal["image_url"] = unsplash_image.get("url_regular")
                    meal["image_source"] = "unsplash"
                    meal["image_photographer"] = unsplash_image.get("photographer")

            enriched.append(meal)
        return enriched


# Singleton instance
_client: Optional[UnsplashClient] = None


def get_unsplash_client() -> UnsplashClient:
    """Get the Unsplash client singleton."""
    global _client
    if _client is None:
        _client = UnsplashClient()
    return _client
