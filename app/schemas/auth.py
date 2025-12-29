"""Authentication schemas."""

from pydantic import BaseModel, Field


class AppleSignInRequest(BaseModel):
    """Request body for Apple Sign-In."""

    identity_token: str = Field(..., description="Apple identity token")
    authorization_code: str | None = Field(None, description="Apple authorization code")
    user_name: str | None = Field(None, description="User's name (first sign-in only)")
    email: str | None = Field(None, description="User's email (if shared)")


class AuthResponse(BaseModel):
    """Authentication response with JWT tokens."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_id: str
    is_new_user: bool = False


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # user_id
    exp: int  # expiration timestamp
    iat: int  # issued at timestamp
