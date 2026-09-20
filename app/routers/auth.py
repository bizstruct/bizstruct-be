from typing import Annotated
from pydantic import ValidationError

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.dependencies import AuthServiceDep
from app.exceptions.auth import AuthenticationError
from app.core.openapi import error_responses
from app.schemas.auth import LoginRequest, RefreshTokenRequest, TokenResponse

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses=error_responses(status.HTTP_503_SERVICE_UNAVAILABLE),
)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(status.HTTP_401_UNAUTHORIZED),
    summary="Authenticate user and get tokens",
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """
        Authenticate a user and return a pair of access and refresh tokens.
    """
    try:
        credentials = LoginRequest(
            email=form_data.username,
            password=form_data.password,
        )
    except ValidationError:
        raise AuthenticationError("Invalid email or password")
    return await auth_service.authenticate(credentials)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(status.HTTP_401_UNAUTHORIZED),
    summary="Refresh access token",
)
async def refresh_tokens(
    data: RefreshTokenRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """
        Validate a refresh token and issue a fresh pair of tokens.
    """
    return await auth_service.refresh_tokens(data.refresh_token)

