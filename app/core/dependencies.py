from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.exceptions.auth import InvalidTokenError
from app.models.user import User
from app.services.auth import AuthService
from app.services.user import UserService


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_user_service(session: DbSession) -> UserService:
    return UserService(session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


def get_auth_service(session: DbSession) -> AuthService:
    return AuthService(session)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_service: UserServiceDep,
) -> User:
    """
        Decodes the access token and fetches the corresponding active user.

        Raises:
            InvalidTokenError: If the token is invalid or the user does not exist.
    """
    payload = decode_token(token, expected_type="access")
    try:
        user = await user_service.get_by_id(payload.sub)
    except Exception as err:
        raise InvalidTokenError("User associated with token no longer exists") from err

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]