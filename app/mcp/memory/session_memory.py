"""Session memory using Redis (L1 memory layer)."""

from datetime import datetime, timezone
from typing import Any

from app.infrastructure.redis import redis_client


class SessionMemory:
    """
    L1 memory layer: Short-term session memory stored in Redis.

    Stores the last N turns of conversation for context.
    """

    MAX_TURNS = 20
    TTL_SECONDS = 3600 * 24  # 24 hours

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self._key = f"session:{session_id}:messages"
        self._meta_key = f"session:{session_id}:meta"

    async def add_message(
        self,
        role: str,
        content: str,
        tool_calls: list[dict] | None = None,
    ) -> None:
        """Add a message to the session history."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if tool_calls:
            message["tool_calls"] = tool_calls

        await redis_client.push_to_list(
            self._key,
            message,
            max_length=self.MAX_TURNS,
        )

        # Update session metadata
        await redis_client.set(
            self._meta_key,
            {
                "user_id": self.user_id,
                "last_activity": datetime.now(timezone.utc).isoformat(),
            },
            expire_seconds=self.TTL_SECONDS,
        )

    async def get_messages(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get recent messages from the session."""
        messages = await redis_client.get_list(self._key)
        if limit:
            messages = messages[-limit:]
        return messages

    async def get_formatted_history(self) -> list[dict[str, str]]:
        """Get messages formatted for the AI model."""
        messages = await self.get_messages()
        return [
            {"role": m["role"], "content": m["content"]}
            for m in messages
        ]

    async def clear(self) -> None:
        """Clear the session history."""
        await redis_client.delete(self._key)
        await redis_client.delete(self._meta_key)

    @classmethod
    async def get_or_create(cls, session_id: str | None, user_id: str) -> "SessionMemory":
        """Get existing session or create a new one."""
        from uuid import uuid4

        if session_id:
            # Verify session belongs to user
            meta = await redis_client.get(f"session:{session_id}:meta")
            if meta and meta.get("user_id") == user_id:
                return cls(session_id, user_id)

        # Create new session
        new_session_id = str(uuid4())
        session = cls(new_session_id, user_id)

        # Initialize metadata
        await redis_client.set(
            session._meta_key,
            {
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_activity": datetime.now(timezone.utc).isoformat(),
            },
            expire_seconds=cls.TTL_SECONDS,
        )

        return session
