"""Challenges endpoints."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import Challenge, ChallengeParticipant, get_db
from app.schemas.progress import (
    ChallengeCreate,
    ChallengeLeaderboard,
    ChallengeParticipantResponse,
    ChallengeResponse,
)

router = APIRouter()


@router.get("/", response_model=list[ChallengeResponse])
async def list_challenges(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = Query(default=True),
    include_joined: bool = Query(default=True),
) -> list[ChallengeResponse]:
    """List available challenges."""
    now = datetime.now(timezone.utc)

    query = select(Challenge)

    if active_only:
        query = query.where(
            Challenge.start_date <= now,
            Challenge.end_date >= now,
        )

    if include_joined:
        # Include public challenges or ones user has joined
        subquery = select(ChallengeParticipant.challenge_id).where(
            ChallengeParticipant.user_id == current_user.id
        )
        query = query.where(
            or_(
                Challenge.is_public == True,
                Challenge.id.in_(subquery),
                Challenge.created_by_user_id == current_user.id,
            )
        )
    else:
        query = query.where(Challenge.is_public == True)

    result = await db.execute(query.order_by(Challenge.end_date.asc()))
    challenges = result.scalars().all()

    responses = []
    for c in challenges:
        # Get participant count
        count_result = await db.execute(
            select(func.count(ChallengeParticipant.id)).where(
                ChallengeParticipant.challenge_id == c.id
            )
        )
        participant_count = count_result.scalar() or 0

        response = ChallengeResponse.model_validate(c)
        response.participant_count = participant_count
        responses.append(response)

    return responses


@router.post("/", response_model=ChallengeResponse, status_code=status.HTTP_201_CREATED)
async def create_challenge(
    current_user: CurrentUser,
    data: ChallengeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChallengeResponse:
    """Create a new challenge."""
    if data.end_date <= data.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date",
        )

    challenge = Challenge(
        created_by_user_id=current_user.id,
        name=data.name,
        description=data.description,
        challenge_type=data.challenge_type,
        target_value=data.target_value,
        start_date=data.start_date,
        end_date=data.end_date,
        is_public=data.is_public,
        max_participants=data.max_participants,
        reward_points=data.reward_points,
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)

    # Creator automatically joins
    participant = ChallengeParticipant(
        challenge_id=challenge.id,
        user_id=current_user.id,
    )
    db.add(participant)
    await db.commit()

    response = ChallengeResponse.model_validate(challenge)
    response.participant_count = 1
    return response


@router.post("/{challenge_id}/join", response_model=ChallengeParticipantResponse)
async def join_challenge(
    challenge_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChallengeParticipantResponse:
    """Join a challenge."""
    # Get challenge
    result = await db.execute(
        select(Challenge).where(Challenge.id == challenge_id)
    )
    challenge = result.scalar_one_or_none()

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )

    # Check if already joined
    existing = await db.execute(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == challenge_id,
            ChallengeParticipant.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already joined this challenge",
        )

    # Check max participants
    if challenge.max_participants:
        count_result = await db.execute(
            select(func.count(ChallengeParticipant.id)).where(
                ChallengeParticipant.challenge_id == challenge_id
            )
        )
        current_count = count_result.scalar() or 0
        if current_count >= challenge.max_participants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Challenge is full",
            )

    participant = ChallengeParticipant(
        challenge_id=challenge_id,
        user_id=current_user.id,
    )
    db.add(participant)
    await db.commit()
    await db.refresh(participant)

    return ChallengeParticipantResponse(
        user_id=current_user.id,
        current_value=0,
        progress_percent=0,
        completed=False,
        completed_at=None,
    )


@router.get("/{challenge_id}/leaderboard", response_model=ChallengeLeaderboard)
async def get_leaderboard(
    challenge_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChallengeLeaderboard:
    """Get challenge leaderboard."""
    # Get challenge
    result = await db.execute(
        select(Challenge).where(Challenge.id == challenge_id)
    )
    challenge = result.scalar_one_or_none()

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )

    # Get participants ordered by progress
    participants_result = await db.execute(
        select(ChallengeParticipant)
        .where(ChallengeParticipant.challenge_id == challenge_id)
        .order_by(ChallengeParticipant.current_value.desc())
    )
    participants = participants_result.scalars().all()

    participant_responses = []
    my_rank = None
    my_progress = None

    for idx, p in enumerate(participants, 1):
        progress_pct = (
            (p.current_value / challenge.target_value) * 100
            if challenge.target_value > 0
            else 0
        )

        response = ChallengeParticipantResponse(
            user_id=p.user_id,
            current_value=p.current_value,
            progress_percent=min(100.0, progress_pct),
            completed=p.completed,
            completed_at=p.completed_at,
            rank=idx,
        )
        participant_responses.append(response)

        if p.user_id == current_user.id:
            my_rank = idx
            my_progress = p.current_value

    return ChallengeLeaderboard(
        challenge=ChallengeResponse.model_validate(challenge),
        participants=participant_responses,
        my_rank=my_rank,
        my_progress=my_progress,
    )


@router.post("/{challenge_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_challenge(
    challenge_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Leave a challenge."""
    result = await db.execute(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == challenge_id,
            ChallengeParticipant.user_id == current_user.id,
        )
    )
    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not participating in this challenge",
        )

    await db.delete(participant)
    await db.commit()


@router.delete("/{challenge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_challenge(
    challenge_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a challenge (creator only)."""
    result = await db.execute(
        select(Challenge).where(
            Challenge.id == challenge_id,
            Challenge.created_by_user_id == current_user.id,
        )
    )
    challenge = result.scalar_one_or_none()

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found or not authorized",
        )

    await db.delete(challenge)
    await db.commit()
