"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://reppy:reppy_dev_password@localhost:5432/reppy"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # AI - Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"

    # JWT Auth
    jwt_secret: str = "dev_secret_change_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # Apple Sign-In
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_bundle_id: str = "com.reppy.app"

    # External APIs
    usda_api_key: str = ""
    exercisedb_api_key: str = ""  # RapidAPI key for ExerciseDB
    spoonacular_api_key: str = ""  # RapidAPI key for Spoonacular
    musclewiki_api_key: str = ""  # MuscleWiki API key for exercise videos
    unsplash_access_key: str = ""  # Unsplash API access key for food images

    # Pipecat / Daily.co (for realtime AI coaching)
    daily_api_key: str = ""
    daily_domain: str = ""
    pipecat_host: str = "0.0.0.0"
    pipecat_port: int = 7860

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
