"""FastAPI server for Pipecat AI Coach."""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional
import aiohttp
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipecat_server.config import config
from pipecat_server.bot import run_bot
from pipecat_server.tools.workout_context import get_session, end_session

app = FastAPI(
    title="Reppy AI Coach",
    description="Real-time AI fitness coaching with Pipecat + Gemini Live",
    version="1.0.0",
)

# CORS for iOS client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track active rooms and bot tasks
active_rooms: dict[str, dict] = {}
bot_tasks: dict[str, asyncio.Task] = {}


class ConnectRequest(BaseModel):
    """Request to start a coaching session."""
    exercise_name: str
    target_sets: int
    target_reps: int
    user_name: Optional[str] = None


class ConnectResponse(BaseModel):
    """Response with room details for iOS client."""
    room_url: str
    token: str  # Changed from room_token - SDK expects 'token'
    room_id: str
    expires_at: str


class SessionStatus(BaseModel):
    """Current session status."""
    room_id: str
    exercise_name: str
    target_sets: int
    target_reps: int
    current_set: int
    current_reps: int
    is_active: bool


async def create_daily_room() -> tuple[str, str]:
    """Create a Daily room and get participant token.

    Returns:
        Tuple of (room_url, participant_token)
    """
    room_name = f"reppy-coach-{uuid.uuid4().hex[:8]}"

    async with aiohttp.ClientSession() as session:
        # Create room
        room_response = await session.post(
            f"{config.daily.api_url}/rooms",
            headers={
                "Authorization": f"Bearer {config.daily.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "name": room_name,
                "privacy": "private",
                "properties": {
                    "exp": int((datetime.now() + timedelta(hours=1)).timestamp()),
                    "enable_chat": False,
                    "enable_knocking": False,
                    "start_video_off": False,
                    "start_audio_off": False,
                },
            },
        )

        if room_response.status != 200:
            error = await room_response.text()
            logger.error(f"Failed to create room: {error}")
            raise HTTPException(status_code=500, detail="Failed to create coaching room")

        room_data = await room_response.json()
        room_url = room_data["url"]
        logger.info(f"Created Daily room: {room_url}")

        # Create participant token
        token_response = await session.post(
            f"{config.daily.api_url}/meeting-tokens",
            headers={
                "Authorization": f"Bearer {config.daily.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "properties": {
                    "room_name": room_name,
                    "is_owner": False,
                    "exp": int((datetime.now() + timedelta(hours=1)).timestamp()),
                    "user_name": "User",
                },
            },
        )

        if token_response.status != 200:
            error = await token_response.text()
            logger.error(f"Failed to create token: {error}")
            raise HTTPException(status_code=500, detail="Failed to create session token")

        token_data = await token_response.json()
        participant_token = token_data["token"]

        # Create owner token for bot
        bot_token_response = await session.post(
            f"{config.daily.api_url}/meeting-tokens",
            headers={
                "Authorization": f"Bearer {config.daily.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "properties": {
                    "room_name": room_name,
                    "is_owner": True,
                    "exp": int((datetime.now() + timedelta(hours=1)).timestamp()),
                    "user_name": "Reppy Coach",
                },
            },
        )

        if bot_token_response.status != 200:
            error = await bot_token_response.text()
            logger.error(f"Failed to create bot token: {error}")
            raise HTTPException(status_code=500, detail="Failed to create bot token")

        bot_token_data = await bot_token_response.json()
        bot_token = bot_token_data["token"]

        return room_url, participant_token, bot_token, room_name


@app.post("/connect", response_model=ConnectResponse)
async def connect(request: ConnectRequest):
    """Start a new AI coaching session.

    Creates a Daily room, starts the bot, and returns credentials for iOS client.
    """
    logger.info(f"Connect request: {request.exercise_name} ({request.target_sets}x{request.target_reps})")

    # Create Daily room
    room_url, participant_token, bot_token, room_name = await create_daily_room()

    # Generate room ID
    room_id = room_name

    # Store room info
    expires_at = datetime.now() + timedelta(hours=1)
    active_rooms[room_id] = {
        "room_url": room_url,
        "exercise_name": request.exercise_name,
        "target_sets": request.target_sets,
        "target_reps": request.target_reps,
        "user_name": request.user_name or "there",
        "created_at": datetime.now().isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    # Start bot in background task
    task = asyncio.create_task(
        run_bot(
            room_url=room_url,
            token=bot_token,
            room_id=room_id,
            exercise_name=request.exercise_name,
            target_sets=request.target_sets,
            target_reps=request.target_reps,
            user_name=request.user_name or "there",
        )
    )
    bot_tasks[room_id] = task

    logger.info(f"Started bot for room {room_id}")

    return ConnectResponse(
        room_url=room_url,
        token=participant_token,
        room_id=room_id,
        expires_at=expires_at.isoformat(),
    )


@app.post("/disconnect/{room_id}")
async def disconnect(room_id: str):
    """End a coaching session."""
    logger.info(f"Disconnect request for room {room_id}")

    if room_id not in active_rooms:
        raise HTTPException(status_code=404, detail="Session not found")

    # Cancel bot task
    if room_id in bot_tasks:
        bot_tasks[room_id].cancel()
        del bot_tasks[room_id]

    # Clean up session data
    end_session(room_id)

    # Remove from active rooms
    del active_rooms[room_id]

    return {"status": "disconnected", "room_id": room_id}


@app.get("/session/{room_id}", response_model=SessionStatus)
async def get_session_status(room_id: str):
    """Get the current status of a coaching session."""
    if room_id not in active_rooms:
        raise HTTPException(status_code=404, detail="Session not found")

    room_info = active_rooms[room_id]
    session = get_session(room_id)

    return SessionStatus(
        room_id=room_id,
        exercise_name=room_info["exercise_name"],
        target_sets=room_info["target_sets"],
        target_reps=room_info["target_reps"],
        current_set=session.current_set if session else 1,
        current_reps=session.current_reps if session else 0,
        is_active=room_id in bot_tasks and not bot_tasks[room_id].done(),
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_sessions": len(active_rooms),
        "config": {
            "daily_configured": bool(config.daily.api_key),
            "gemini_configured": bool(config.gemini.api_key),
        },
    }


@app.on_event("startup")
async def startup():
    """Startup tasks."""
    logger.info("Starting Reppy AI Coach server")
    logger.info(f"Daily domain: {config.daily.domain}")
    logger.info(f"Gemini model: {config.gemini.model}")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    logger.info("Shutting down Reppy AI Coach server")

    # Cancel all bot tasks
    for room_id, task in bot_tasks.items():
        task.cancel()
        logger.info(f"Cancelled bot for room {room_id}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "pipecat_server.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.debug,
    )
