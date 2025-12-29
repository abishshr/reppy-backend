"""Memory tools for learning user preferences from conversations."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import UserMemory
from app.mcp.tools.base import BaseTool, ToolResult


class LearnFactTool(BaseTool):
    """
    Store a learned fact about the user from the conversation.

    The AI calls this when it learns something new about the user's
    preferences, habits, or personal information that should be remembered.
    """

    name = "learn_user_fact"
    description = """Store a learned fact about the user that should be remembered
    for future conversations. Use this when the user mentions preferences, habits,
    schedules, dislikes, health conditions, or any other personal information that
    would help personalize future interactions.

    Examples of facts to learn:
    - "Doesn't like broccoli"
    - "Works out in the morning before work"
    - "Training for a marathon in March"
    - "Lactose intolerant"
    - "Prefers high-protein meals"
    - "Usually has lunch around 1pm"
    """

    parameters = {
        "category": {
            "type": "string",
            "description": "Category of the fact: food_preference, food_dislike, workout_habit, schedule, health_note, goal, other",
            "required": True,
        },
        "fact": {
            "type": "string",
            "description": "The fact to remember about the user, written in third person (e.g., 'Prefers low-carb meals')",
            "required": True,
        },
        "confidence": {
            "type": "number",
            "description": "How confident are you about this fact (0.0-1.0). Use 0.9+ for explicit statements, 0.7-0.8 for inferred preferences",
            "required": False,
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Store the learned fact in the database."""
        category = kwargs.get("category", "other")
        fact = kwargs.get("fact", "")
        confidence = kwargs.get("confidence", 0.8)

        if not fact:
            return ToolResult(
                success=False,
                error="No fact provided to learn",
            )

        # Validate category
        valid_categories = [
            "food_preference", "food_dislike", "workout_habit",
            "schedule", "health_note", "goal", "other"
        ]
        if category not in valid_categories:
            category = "other"

        # Check for duplicate or similar facts
        existing = await self.db.execute(
            select(UserMemory).where(
                UserMemory.user_id == self.user_id,
                UserMemory.category == category,
                UserMemory.fact == fact,
                UserMemory.is_active == True,
            )
        )
        if existing.scalar_one_or_none():
            return ToolResult(
                success=True,
                data={"status": "already_known", "fact": fact},
            )

        # Store the new fact
        memory = UserMemory(
            user_id=self.user_id,
            category=category,
            fact=fact,
            confidence=min(max(confidence, 0.0), 1.0),
            source="chat",
        )
        self.db.add(memory)
        await self.db.flush()

        return ToolResult(
            success=True,
            data={
                "status": "learned",
                "category": category,
                "fact": fact,
                "memory_id": memory.id,
            },
        )


class GetUserMemoriesTools(BaseTool):
    """
    Retrieve learned facts about the user.

    This is used internally to load user memories for context.
    """

    name = "get_user_memories"
    description = "Retrieve stored facts and preferences about the user."

    parameters = {
        "category": {
            "type": "string",
            "description": "Optional category to filter by",
            "required": False,
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Get user's stored memories."""
        category = kwargs.get("category")

        query = select(UserMemory).where(
            UserMemory.user_id == self.user_id,
            UserMemory.is_active == True,
        ).order_by(UserMemory.created_at.desc())

        if category:
            query = query.where(UserMemory.category == category)

        result = await self.db.execute(query)
        memories = result.scalars().all()

        return ToolResult(
            success=True,
            data={
                "memories": [
                    {
                        "category": m.category,
                        "fact": m.fact,
                        "confidence": m.confidence,
                    }
                    for m in memories
                ],
                "count": len(memories),
            },
        )
