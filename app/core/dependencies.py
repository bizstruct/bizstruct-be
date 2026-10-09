from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.core.config import settings
from app.exceptions.auth import InvalidTokenError
from app.models.user import User
from app.ports.events import EventPort
from app.ports.queue import QueuePort
from app.pubsub import WebPubSubEvents
from app.servicebus import ServiceBusQueue
from app.services.auth import AuthService
from app.services.orchestrator import GenerationOrchestrator
from app.services.project import ProjectService
from app.services.stage import StageService
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


def get_project_service(session: DbSession) -> ProjectService:
    return ProjectService(session)


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]


def get_stage_service(session: DbSession) -> StageService:
    return StageService(session)


StageServiceDep = Annotated[StageService, Depends(get_stage_service)]


def get_queue() -> QueuePort:
    return ServiceBusQueue()


def get_events() -> EventPort:
    return WebPubSubEvents()


def get_orchestrator(
    session: DbSession,
    stage_service: StageServiceDep,
    queue: Annotated[QueuePort, Depends(get_queue)],
    events: Annotated[EventPort, Depends(get_events)],
) -> GenerationOrchestrator:
    return GenerationOrchestrator(
        session,
        stage_service,
        queue,
        events,
        stuck_timeout_seconds=settings.stuck_timeout_seconds,
    )


OrchestratorDep = Annotated[GenerationOrchestrator, Depends(get_orchestrator)]


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

    if not user.is_active:
        raise InvalidTokenError("User account is inactive")

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]

