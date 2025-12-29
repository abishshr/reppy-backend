"""Social features endpoints - friends, activity feed, reactions."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import CurrentUser
from app.infrastructure.database import (
    ActivityFeedItem,
    ActivityReaction,
    Friendship,
    User,
    get_db,
)
from app.schemas.progress import (
    ActivityFeedItemResponse,
    FriendRequest,
    FriendshipResponse,
    ReactionCreate,
)

router = APIRouter()


# =============================================================================
# Friends
# =============================================================================


@router.get("/friends", response_model=list[FriendshipResponse])
async def list_friends(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(None, pattern="^(pending|accepted)$"),
) -> list[FriendshipResponse]:
    """List friends and friend requests."""
    query = select(Friendship).where(
        or_(
            Friendship.user_id == current_user.id,
            Friendship.friend_id == current_user.id,
        )
    )

    if status_filter:
        query = query.where(Friendship.status == status_filter)

    result = await db.execute(query.order_by(Friendship.created_at.desc()))
    friendships = result.scalars().all()

    responses = []
    for f in friendships:
        # Get the friend's name
        other_id = f.friend_id if f.user_id == current_user.id else f.user_id
        user_result = await db.execute(select(User).where(User.id == other_id))
        other_user = user_result.scalar_one_or_none()

        response = FriendshipResponse.model_validate(f)
        response.friend_name = other_user.name if other_user else None
        responses.append(response)

    return responses


@router.post("/friends", response_model=FriendshipResponse, status_code=status.HTTP_201_CREATED)
async def send_friend_request(
    current_user: CurrentUser,
    data: FriendRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FriendshipResponse:
    """Send a friend request."""
    if data.friend_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add yourself as a friend",
        )

    # Check if user exists
    user_result = await db.execute(select(User).where(User.id == data.friend_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if friendship already exists
    existing = await db.execute(
        select(Friendship).where(
            or_(
                and_(
                    Friendship.user_id == current_user.id,
                    Friendship.friend_id == data.friend_id,
                ),
                and_(
                    Friendship.user_id == data.friend_id,
                    Friendship.friend_id == current_user.id,
                ),
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Friend request already exists",
        )

    friendship = Friendship(
        user_id=current_user.id,
        friend_id=data.friend_id,
        status="pending",
    )
    db.add(friendship)
    await db.commit()
    await db.refresh(friendship)

    return FriendshipResponse.model_validate(friendship)


@router.post("/friends/{friendship_id}/accept", response_model=FriendshipResponse)
async def accept_friend_request(
    friendship_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FriendshipResponse:
    """Accept a friend request."""
    result = await db.execute(
        select(Friendship).where(
            Friendship.id == friendship_id,
            Friendship.friend_id == current_user.id,
            Friendship.status == "pending",
        )
    )
    friendship = result.scalar_one_or_none()

    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend request not found",
        )

    friendship.status = "accepted"
    friendship.accepted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(friendship)

    return FriendshipResponse.model_validate(friendship)


@router.delete("/friends/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend(
    friendship_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove a friend or decline a request."""
    result = await db.execute(
        select(Friendship).where(
            Friendship.id == friendship_id,
            or_(
                Friendship.user_id == current_user.id,
                Friendship.friend_id == current_user.id,
            ),
        )
    )
    friendship = result.scalar_one_or_none()

    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friendship not found",
        )

    await db.delete(friendship)
    await db.commit()


# =============================================================================
# Activity Feed
# =============================================================================


@router.get("/feed", response_model=list[ActivityFeedItemResponse])
async def get_activity_feed(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ActivityFeedItemResponse]:
    """Get activity feed from friends."""
    # Get friend IDs
    friends_result = await db.execute(
        select(Friendship).where(
            or_(
                Friendship.user_id == current_user.id,
                Friendship.friend_id == current_user.id,
            ),
            Friendship.status == "accepted",
        )
    )
    friendships = friends_result.scalars().all()

    friend_ids = set()
    for f in friendships:
        if f.user_id == current_user.id:
            friend_ids.add(f.friend_id)
        else:
            friend_ids.add(f.user_id)

    # Include own activities
    friend_ids.add(current_user.id)

    # Get activities
    result = await db.execute(
        select(ActivityFeedItem)
        .where(
            ActivityFeedItem.user_id.in_(friend_ids),
            or_(
                ActivityFeedItem.visibility == "public",
                ActivityFeedItem.visibility == "friends",
                ActivityFeedItem.user_id == current_user.id,
            ),
        )
        .order_by(ActivityFeedItem.created_at.desc())
        .limit(limit)
    )
    activities = result.scalars().all()

    responses = []
    for activity in activities:
        # Get reaction count
        count_result = await db.execute(
            select(func.count(ActivityReaction.id)).where(
                ActivityReaction.activity_id == activity.id
            )
        )
        reaction_count = count_result.scalar() or 0

        # Check if user has reacted
        user_reaction = await db.execute(
            select(ActivityReaction).where(
                ActivityReaction.activity_id == activity.id,
                ActivityReaction.user_id == current_user.id,
            )
        )
        has_reacted = user_reaction.scalar_one_or_none() is not None

        # Get user name
        user_result = await db.execute(
            select(User).where(User.id == activity.user_id)
        )
        user = user_result.scalar_one_or_none()

        response = ActivityFeedItemResponse.model_validate(activity)
        response.reaction_count = reaction_count
        response.has_reacted = has_reacted
        response.user_name = user.name if user else None
        responses.append(response)

    return responses


@router.post("/feed/{activity_id}/react", status_code=status.HTTP_201_CREATED)
async def react_to_activity(
    activity_id: str,
    data: ReactionCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Add a reaction to an activity."""
    # Check activity exists
    activity_result = await db.execute(
        select(ActivityFeedItem).where(ActivityFeedItem.id == activity_id)
    )
    if not activity_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    # Check if already reacted
    existing = await db.execute(
        select(ActivityReaction).where(
            ActivityReaction.activity_id == activity_id,
            ActivityReaction.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already reacted to this activity",
        )

    reaction = ActivityReaction(
        activity_id=activity_id,
        user_id=current_user.id,
        reaction_type=data.reaction_type,
    )
    db.add(reaction)
    await db.commit()

    return {"status": "ok", "reaction_type": data.reaction_type}


@router.delete("/feed/{activity_id}/react", status_code=status.HTTP_204_NO_CONTENT)
async def remove_reaction(
    activity_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove a reaction from an activity."""
    result = await db.execute(
        select(ActivityReaction).where(
            ActivityReaction.activity_id == activity_id,
            ActivityReaction.user_id == current_user.id,
        )
    )
    reaction = result.scalar_one_or_none()

    if not reaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reaction not found",
        )

    await db.delete(reaction)
    await db.commit()
