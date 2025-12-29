"""Dependency injection configuration."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.ai.gemini_client import GeminiClient
from app.infrastructure.database import get_db


def get_gemini_client() -> GeminiClient:
    """Get Gemini AI client."""
    return GeminiClient()


# Type aliases for dependency injection
Database = Annotated[AsyncSession, Depends(get_db)]
AIClient = Annotated[GeminiClient, Depends(get_gemini_client)]
