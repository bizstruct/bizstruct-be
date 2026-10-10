import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)

from app.exceptions.auth import AuthenticationError, InvalidTokenError
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse


logger = structlog.get_logger(__name__)


class AuthService:
    """
        Service handling user authentication and token lifecycle.
    """
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def _get_user_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def authenticate(self, credentials: LoginRequest) -> TokenResponse:
        """
            Validates credentials and returns access and refresh tokens.

            Raises:
                AuthenticationError: If email not found or password does not match.
        """
        user = await self._get_user_by_email(credentials.email)
        
        if not user or not verify_password(credentials.password, user.password_hash):
            logger.warning(
                "authentication_failed",
                email=credentials.email,
            )
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            logger.warning(
                "inactive_user_login_attempt",
                user_id=str(user.id),
            )
            raise AuthenticationError("User account is inactive")


        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        logger.info(
            "user_authenticated",
            user_id=str(user.id),
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )
    
    async def refresh_tokens(self, refresh_token_str: str) -> TokenResponse:
        """
            Validates a refresh token and generates a new token pair.

            Raises:
                InvalidTokenError: If token is expired or invalid.
                AuthenticationError: If the user associated with the token no longer exists.
        """
        payload = decode_token(refresh_token_str, expected_type="refresh")

        statement = select(User).where(User.id == payload.sub)
        result = await self._session.execute(statement)
        user = result.scalar_one_or_none()
        
        if not user:
            raise InvalidTokenError("User associated with token no longer exists")

        new_access_token = create_access_token(user.id)
        new_refresh_token = create_refresh_token(user.id)

        logger.info(
            "tokens_refreshed",
            user_id=str(user.id),
        )

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )

