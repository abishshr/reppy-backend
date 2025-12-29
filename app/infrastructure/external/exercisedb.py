"""ExerciseDB API client for exercise images and information."""

import httpx
from functools import lru_cache
from typing import Optional

from app.config import settings


class ExerciseDBClient:
    """Client for ExerciseDB API (RapidAPI)."""

    BASE_URL = "https://exercisedb.p.rapidapi.com"

    def __init__(self):
        self.api_key = settings.exercisedb_api_key
        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "exercisedb.p.rapidapi.com",
        }
        self._cache: dict[str, dict] = {}

    def _build_gif_url(self, exercise_id: str, resolution: int = 360) -> str:
        """Build the GIF URL for an exercise.

        Resolution options:
        - 180: Available on Basic (free) tier
        - 360: Available on Pro tier and above
        - 720, 1080: Available on Ultra/Mega tiers
        """
        return f"{self.BASE_URL}/image?exerciseId={exercise_id}&resolution={resolution}&rapidapi-key={self.api_key}"

    async def search_exercise(self, name: str) -> Optional[dict]:
        """
        Search for an exercise by name and return its details including GIF URL.

        Returns dict with: id, name, gif_url, target, bodyPart, equipment, instructions
        """
        if not self.api_key:
            return None

        # Check cache first
        cache_key = name.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            async with httpx.AsyncClient() as client:
                # Search by name
                response = await client.get(
                    f"{self.BASE_URL}/exercises/name/{cache_key}",
                    headers=self.headers,
                    params={"limit": 1},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    exercises = response.json()
                    if exercises and len(exercises) > 0:
                        exercise = exercises[0]
                        exercise_id = exercise.get("id")
                        result = {
                            "id": exercise_id,
                            "name": exercise.get("name"),
                            "gif_url": self._build_gif_url(exercise_id, 180) if exercise_id else None,
                            "target_muscle": exercise.get("target"),
                            "body_part": exercise.get("bodyPart"),
                            "equipment": exercise.get("equipment"),
                            "instructions": exercise.get("instructions", []),
                            "secondary_muscles": exercise.get("secondaryMuscles", []),
                        }
                        self._cache[cache_key] = result
                        return result

        except Exception as e:
            print(f"ExerciseDB API error: {e}")

        return None

    async def get_exercise_by_id(self, exercise_id: str) -> Optional[dict]:
        """Get exercise details by ExerciseDB ID."""
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/exercises/exercise/{exercise_id}",
                    headers=self.headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    exercise = response.json()
                    return {
                        "id": exercise_id,
                        "name": exercise.get("name"),
                        "gif_url": self._build_gif_url(exercise_id, 180),
                        "target_muscle": exercise.get("target"),
                        "body_part": exercise.get("bodyPart"),
                        "equipment": exercise.get("equipment"),
                        "instructions": exercise.get("instructions", []),
                        "secondary_muscles": exercise.get("secondaryMuscles", []),
                    }

        except Exception as e:
            print(f"ExerciseDB API error: {e}")

        return None

    async def enrich_exercises(self, exercises: list[dict]) -> list[dict]:
        """
        Enrich a list of exercises with images and instructions from ExerciseDB.

        Takes exercises with 'name' field and adds 'gif_url', 'instructions', etc.
        """
        enriched = []
        for exercise in exercises:
            name = exercise.get("name", "")
            if name:
                db_exercise = await self.search_exercise(name)
                if db_exercise:
                    exercise["gif_url"] = db_exercise.get("gif_url")
                    exercise["target_muscle"] = db_exercise.get("target_muscle")
                    exercise["instructions"] = db_exercise.get("instructions", [])
                    exercise["secondary_muscles"] = db_exercise.get("secondary_muscles", [])
            enriched.append(exercise)
        return enriched


# Singleton instance
_client: Optional[ExerciseDBClient] = None


def get_exercisedb_client() -> ExerciseDBClient:
    """Get the ExerciseDB client singleton."""
    global _client
    if _client is None:
        _client = ExerciseDBClient()
    return _client
