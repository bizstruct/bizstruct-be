from uuid import UUID

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """
    Request model for user login.
    """
    
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """
        Response model for authentication tokens.
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """
        Payload model for JWT tokens.
    """
    sub: UUID
    type: str
    iat: int
    exp: int


class RefreshTokenRequest(BaseModel):
    """
        Request model for refreshing access tokens.
    """
    refresh_token: str