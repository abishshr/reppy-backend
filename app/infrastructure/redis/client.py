"""Redis client for session memory and caching."""

import json
from typing import Any

import redis.asyncio as redis

from app.config import settings


class RedisClient:
    """Async Redis client wrapper."""

    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        self._client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()

    @property
    def client(self) -> redis.Redis:
        """Get the Redis client."""
        if self._client is None:
            raise RuntimeError("Redis client not connected")
        return self._client

    async def set(
        self,
        key: str,
        value: Any,
        expire_seconds: int | None = None,
    ) -> None:
        """Set a value in Redis."""
        serialized = json.dumps(value) if not isinstance(value, str) else value
        if expire_seconds:
            await self.client.setex(key, expire_seconds, serialized)
        else:
            await self.client.set(key, serialized)

    async def get(self, key: str) -> Any | None:
        """Get a value from Redis."""
        value = await self.client.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def delete(self, key: str) -> None:
        """Delete a key from Redis."""
        await self.client.delete(key)

    async def push_to_list(
        self,
        key: str,
        value: Any,
        max_length: int | None = None,
    ) -> None:
        """Push a value to a list (for conversation history)."""
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await self.client.rpush(key, serialized)
        if max_length:
            await self.client.ltrim(key, -max_length, -1)

    async def get_list(self, key: str, start: int = 0, end: int = -1) -> list[Any]:
        """Get a list from Redis."""
        items = await self.client.lrange(key, start, end)
        result = []
        for item in items:
            try:
                result.append(json.loads(item))
            except json.JSONDecodeError:
                result.append(item)
        return result

    async def set_hash(self, key: str, mapping: dict[str, Any]) -> None:
        """Set a hash in Redis."""
        serialized = {k: json.dumps(v) if not isinstance(v, str) else v for k, v in mapping.items()}
        await self.client.hset(key, mapping=serialized)

    async def get_hash(self, key: str) -> dict[str, Any]:
        """Get a hash from Redis."""
        data = await self.client.hgetall(key)
        result = {}
        for k, v in data.items():
            try:
                result[k] = json.loads(v)
            except json.JSONDecodeError:
                result[k] = v
        return result


redis_client = RedisClient()
