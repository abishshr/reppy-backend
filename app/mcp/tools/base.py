"""Base tool class for MCP tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    requires_confirmation: bool = False
    suggestion_id: str | None = None


class BaseTool(ABC):
    """Base class for all MCP tools."""

    name: str
    description: str
    parameters: dict[str, Any]

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given parameters."""
        pass

    def get_schema(self) -> dict[str, Any]:
        """Get the tool schema for the AI model."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": [
                    k for k, v in self.parameters.items()
                    if not v.get("optional", False)
                ],
            },
        }
