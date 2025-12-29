"""Profile and context tools for MCP."""

from typing import Any

from app.mcp.context_assembler import ContextAssembler
from app.mcp.tools.base import BaseTool, ToolResult


class GetUserContextTool(BaseTool):
    """Get user's profile and context for personalized responses."""

    name = "get_user_context"
    description = """Retrieve the user's profile, goals, dietary preferences,
    allergies, recent meals, workouts, and activity data. Use this to provide
    personalized coaching and recommendations."""

    parameters = {}  # No parameters needed

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Get comprehensive user context."""
        assembler = ContextAssembler(self.db)
        context = await assembler.assemble_context(self.user_id)

        return ToolResult(
            success=True,
            data=context,
        )
