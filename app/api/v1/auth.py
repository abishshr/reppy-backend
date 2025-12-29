"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import create_access_token, verify_apple_token
from app.infrastructure.database import User, UserProfile, get_db
from app.schemas import AppleSignInRequest, AuthResponse

router = APIRouter()


@router.post("/apple", response_model=AuthResponse)
async def sign_in_with_apple(
    request: AppleSignInRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """
    Sign in with Apple.

    Verifies the Apple identity token and creates/retrieves the user.
    """
    # Verify the Apple token
    apple_data = await verify_apple_token(request.identity_token)
    apple_id = apple_data["apple_id"]

    # Check if user exists
    result = await db.execute(select(User).where(User.apple_id == apple_id))
    user = result.scalar_one_or_none()

    is_new_user = False

    if not user:
        # Create new user
        user = User(
            apple_id=apple_id,
            email=request.email or apple_data.get("email"),
        )
        db.add(user)
        await db.flush()

        # Create empty profile
        profile = UserProfile(
            user_id=user.id,
            name=request.user_name,
        )
        db.add(profile)
        is_new_user = True

    await db.commit()
    await db.refresh(user)

    # Generate JWT
    access_token = create_access_token(data={"sub": user.id})

    return AuthResponse(
        access_token=access_token,
        expires_in=settings.jwt_expiration_hours * 3600,
        user_id=user.id,
        is_new_user=is_new_user,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    # In a real app, you'd use a refresh token here
    # For simplicity, we'll just require re-authentication
) -> AuthResponse:
    """Refresh access token (placeholder - requires proper refresh token flow)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Token refresh not yet implemented. Please re-authenticate.",
    )


@router.post("/dev", response_model=AuthResponse)
async def dev_login(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """
    Development login endpoint - creates/retrieves a test user.
    Only available when ENVIRONMENT=development.
    """
    if settings.environment != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev login only available in development environment",
        )

    dev_apple_id = "dev_user_simulator"

    # Check if dev user exists
    result = await db.execute(select(User).where(User.apple_id == dev_apple_id))
    user = result.scalar_one_or_none()

    is_new_user = False

    if not user:
        # Create dev user
        user = User(
            apple_id=dev_apple_id,
            email="dev@reppy.local",
        )
        db.add(user)
        await db.flush()

        # Create profile
        profile = UserProfile(
            user_id=user.id,
            name="Dev User",
        )
        db.add(profile)
        is_new_user = True

    await db.commit()
    await db.refresh(user)

    # Generate JWT
    access_token = create_access_token(data={"sub": user.id})

    return AuthResponse(
        access_token=access_token,
        expires_in=settings.jwt_expiration_hours * 3600,
        user_id=user.id,
        is_new_user=is_new_user,
    )
