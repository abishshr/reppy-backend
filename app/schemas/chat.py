"""Chat and conversation schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single chat message."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime | None = None


class ChatRequest(BaseModel):
    """Request body for sending a chat message."""

    message: str = Field(..., min_length=1, max_length=5000)
    session_id: str | None = None  # For continuing a conversation
    # Image support for meal photo analysis
    image_url: str | None = None  # Public URL of uploaded image
    image_base64: str | None = None  # Base64-encoded image data
    image_mime_type: str | None = None  # e.g., "image/jpeg", "image/png"


class ToolCallResult(BaseModel):
    """Result of a tool call from the AI."""

    tool_name: str
    status: Literal["success", "error", "pending_confirmation"]
    result: dict[str, Any] | None = None
    error: str | None = None
    requires_confirmation: bool = False
    suggestion_id: str | None = None


class ChatResponse(BaseModel):
    """Response body for a chat message."""

    message: str
    session_id: str
    tool_calls: list[ToolCallResult] = Field(default_factory=list)
    pending_confirmation: dict[str, Any] | None = None
    # If a suggestion needs confirmation, include it here
