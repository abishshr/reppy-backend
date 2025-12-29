"""MuscleWiki API client for exercise videos and demonstrations."""

import httpx
from typing import Optional

from app.config import settings


class MuscleWikiClient:
    """Client for MuscleWiki API - exercise videos and demonstrations.

    MuscleWiki provides high-quality exercise demonstration videos
    with male/female variants and detailed muscle targeting info.
    """

    BASE_URL = "https://musclewiki.com/api"

    def __init__(self):
        self.api_key = settings.musclewiki_api_key
        self._cache: dict[str, dict] = {}

    def _get_headers(self) -> dict:
        """Get request headers with API key if available."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def search_exercise(
        self,
        name: str,
        gender: str = "male",
        limit: int = 5
    ) -> Optional[dict]:
        """
        Search for an exercise by name and return its details including video URL.

        Args:
            name: Exercise name to search for
            gender: "male" or "female" for video variant
            limit: Maximum number of results

        Returns dict with: id, name, video_url, target_muscles, equipment, instructions
        """
        # Check cache first
        cache_key = f"{name.lower().strip()}:{gender}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            async with httpx.AsyncClient() as client:
                # Search exercises endpoint
                response = await client.get(
                    f"{self.BASE_URL}/exercises/search",
                    headers=self._get_headers(),
                    params={
                        "name": name,
                        "limit": limit,
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    exercises = data.get("exercises", data) if isinstance(data, dict) else data

                    if exercises and len(exercises) > 0:
                        exercise = exercises[0]

                        # Get video URL based on gender preference
                        videos = exercise.get("videos", {})
                        video_url = videos.get(gender) or videos.get("male") or videos.get("default")

                        result = {
                            "id": exercise.get("id"),
                            "name": exercise.get("name"),
                            "video_url": video_url,
                            "target_muscles": exercise.get("target_muscles", []),
                            "secondary_muscles": exercise.get("secondary_muscles", []),
                            "equipment": exercise.get("equipment"),
                            "difficulty": exercise.get("difficulty"),
                            "instructions": exercise.get("instructions", []),
                            "tips": exercise.get("tips", []),
                        }
                        self._cache[cache_key] = result
                        return result

        except httpx.TimeoutException:
            print(f"MuscleWiki API timeout for: {name}")
        except Exception as e:
            print(f"MuscleWiki API error: {e}")

        return None

    async def get_exercises_by_muscle(
        self,
        muscle: str,
        equipment: Optional[str] = None,
        limit: int = 20
    ) -> list[dict]:
        """
        Get exercises targeting a specific muscle group.

        Args:
            muscle: Target muscle (e.g., "chest", "biceps", "quadriceps")
            equipment: Optional equipment filter
            limit: Maximum number of results

        Returns list of exercises with video URLs
        """
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "muscle": muscle,
                    "limit": limit,
                }
                if equipment:
                    params["equipment"] = equipment

                response = await client.get(
                    f"{self.BASE_URL}/exercises",
                    headers=self._get_headers(),
                    params=params,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    exercises = data.get("exercises", data) if isinstance(data, dict) else data

                    return [
                        {
                            "id": ex.get("id"),
                            "name": ex.get("name"),
                            "video_url": ex.get("videos", {}).get("male"),
                            "target_muscles": ex.get("target_muscles", []),
                            "equipment": ex.get("equipment"),
                            "difficulty": ex.get("difficulty"),
                        }
                        for ex in exercises
                    ]

        except Exception as e:
            print(f"MuscleWiki API error: {e}")

        return []

    async def enrich_exercises_with_videos(
        self,
        exercises: list[dict],
        gender: str = "male"
    ) -> list[dict]:
        """
        Enrich a list of exercises with video URLs from MuscleWiki.

        Takes exercises with 'name' field and adds 'video_url'.
        Falls back to existing gif_url if video not found.
        """
        enriched = []
        for exercise in exercises:
            name = exercise.get("name", "")
            if name:
                mw_exercise = await self.search_exercise(name, gender=gender)
                if mw_exercise and mw_exercise.get("video_url"):
                    exercise["video_url"] = mw_exercise.get("video_url")
                    # Also update target muscles if not set
                    if not exercise.get("target_muscle") and mw_exercise.get("target_muscles"):
                        exercise["target_muscle"] = mw_exercise["target_muscles"][0] if mw_exercise["target_muscles"] else None
            enriched.append(exercise)
        return enriched


# Singleton instance
_client: Optional[MuscleWikiClient] = None


def get_musclewiki_client() -> MuscleWikiClient:
    """Get the MuscleWiki client singleton."""
    global _client
    if _client is None:
        _client = MuscleWikiClient()
    return _client
