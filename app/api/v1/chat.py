"""Chat endpoints for AI interactions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.ai.gemini_client import GeminiClient
from app.infrastructure.database import get_db
from app.mcp.orchestrator import MCPOrchestrator
from app.schemas import ChatRequest, ChatResponse, ToolCallResult

router = APIRouter()


def get_gemini_client() -> GeminiClient:
    """Dependency for Gemini client."""
    return GeminiClient()


@router.post("", response_model=ChatResponse)
async def send_message(
    current_user: CurrentUser,
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
) -> ChatResponse:
    """
    Send a message to the AI coach.

    The AI will parse meal/workout descriptions and use tools to create
    structured logs. Logs require confirmation before being saved.
    """
    orchestrator = MCPOrchestrator(
        db=db,
        user_id=current_user.id,
        gemini_client=gemini,
    )

    result = await orchestrator.process_message(
        message=request.message,
        session_id=request.session_id,
        image_url=request.image_url,
        image_base64=request.image_base64,
        image_mime_type=request.image_mime_type,
    )

    return ChatResponse(
        message=result["message"],
        session_id=result["session_id"],
        tool_calls=[
            ToolCallResult(
                tool_name=tc["tool_name"],
                status=tc["status"],
                result=tc.get("result"),
                error=tc.get("error"),
                requires_confirmation=tc.get("requires_confirmation", False),
                suggestion_id=tc.get("suggestion_id"),
            )
            for tc in result.get("tool_calls", [])
        ],
        pending_confirmation=result.get("pending_confirmation"),
    )


@router.post("/confirm")
async def confirm_suggestion(
    current_user: CurrentUser,
    suggestion_type: str,  # "meal" or "workout"
    suggestion_id: str,
    session_id: str | None = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)] = None,
) -> dict:
    """
    Confirm a pending meal or workout suggestion.

    After the AI suggests a meal/workout log, the user must confirm
    before it's saved to the database.
    """
    if suggestion_type not in ("meal", "workout"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="suggestion_type must be 'meal' or 'workout'",
        )

    orchestrator = MCPOrchestrator(
        db=db,
        user_id=current_user.id,
        gemini_client=gemini,
    )

    result = await orchestrator.confirm_suggestion(
        suggestion_type=suggestion_type,
        suggestion_id=suggestion_id,
        session_id=session_id,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to confirm suggestion"),
        )

    await db.commit()

    return {
        "success": True,
        "message": f"{suggestion_type.capitalize()} logged successfully",
        "data": result.get("data"),
    }
