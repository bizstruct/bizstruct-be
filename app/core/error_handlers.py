import structlog

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions.auth import AuthenticationError
from app.exceptions.base import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
)

from app.schemas.common import ErrorResponse


logger = structlog.get_logger(__name__)


async def authentication_error_handler(
    request: Request, exc: AuthenticationError
) -> JSONResponse:
    logger.warning(
        exc.__class__.__name__,
        path=request.url.path,
        detail=exc.message,
    )
    payload = ErrorResponse(detail=exc.message).model_dump()
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=payload,
        headers={"WWW-Authenticate": "Bearer"},
    )

async def entity_not_found_handler(
    request: Request, exc: EntityNotFoundError
) -> JSONResponse:
    logger.warning(
        exc.__class__.__name__,
        path=request.url.path,
        detail=exc.message,
    )
    payload = ErrorResponse(detail=exc.message).model_dump()
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=payload,
    )


async def entity_already_exists_handler(
    request: Request, exc: EntityAlreadyExistsError
) -> JSONResponse:
    logger.warning(
        exc.__class__.__name__,
        path=request.url.path,
        detail=exc.message,
    )
    payload = ErrorResponse(detail=exc.message).model_dump()
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=payload,
    )


async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.error(
        exc.__class__.__name__,
        path=request.url.path,
        exc_info=exc,
    )
    payload = ErrorResponse(
        detail="Database service is temporarily unavailable"
    ).model_dump()
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
        Register all global exception handlers.
    """
    app.add_exception_handler(AuthenticationError, authentication_error_handler)
    app.add_exception_handler(EntityNotFoundError, entity_not_found_handler)
    app.add_exception_handler(EntityAlreadyExistsError, entity_already_exists_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)