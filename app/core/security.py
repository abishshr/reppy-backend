"""Security utilities for authentication and authorization."""

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from app.config import settings
from app.core.exceptions import AuthenticationError

# Apple's public keys endpoint
APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.jwt_expiration_hours)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {e}")


async def verify_apple_token(identity_token: str) -> dict[str, Any]:
    """
    Verify an Apple Sign-In identity token.

    Returns the decoded token payload containing:
    - sub: Apple user ID
    - email: User email (if shared)
    - email_verified: Whether email is verified
    """
    try:
        # Get Apple's public keys
        jwks_client = PyJWKClient(APPLE_KEYS_URL)

        # Get the signing key from the token header
        signing_key = jwks_client.get_signing_key_from_jwt(identity_token)

        # Decode and verify the token
        payload = jwt.decode(
            identity_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.apple_bundle_id,
            issuer="https://appleid.apple.com",
        )

        return {
            "apple_id": payload.get("sub"),
            "email": payload.get("email"),
            "email_verified": payload.get("email_verified", False),
        }

    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Apple token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid Apple token: {e}")
    except Exception as e:
        raise AuthenticationError(f"Failed to verify Apple token: {e}")


async def fetch_apple_public_keys() -> dict[str, Any]:
    """Fetch Apple's public keys for token verification."""
    async with httpx.AsyncClient() as client:
        response = await client.get(APPLE_KEYS_URL)
        response.raise_for_status()
        return response.json()
