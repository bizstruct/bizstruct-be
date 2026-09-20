from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.dependencies import CurrentUserDep, UserServiceDep
from app.core.openapi import error_responses
from app.schemas.user import UserCreate, UserResponse, UserUpdate


router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses=error_responses(status.HTTP_503_SERVICE_UNAVAILABLE),
)


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(status.HTTP_409_CONFLICT),
    summary="Create a new user",
)
async def create_user(
    data: UserCreate,
    service: UserServiceDep,
) -> UserResponse:
    user = await service.create(data)
    return UserResponse.model_validate(user)


@router.get(
    "/",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
    responses=error_responses(status.HTTP_401_UNAUTHORIZED),
    summary="List users",
)
async def list_users(
    _: CurrentUserDep,
    service: UserServiceDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> Sequence[UserResponse]:
    users = await service.list_users(skip=skip, limit=limit)
    return [UserResponse.model_validate(user) for user in users]


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(status.HTTP_401_UNAUTHORIZED),
    summary="Get current logged-in user profile",
)
async def get_me(
    current_user: CurrentUserDep,
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
    summary="Update own profile",
)
async def update_current_user(
    data: UserUpdate,
    service: UserServiceDep,
    current_user: CurrentUserDep,
) -> UserResponse:
    user = await service.update(user_id=current_user.id, data=data)
    return UserResponse.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
    ),
    summary="Get user by ID",
)
async def get_user_by_id(
    user_id: UUID,
    _: CurrentUserDep,
    service: UserServiceDep,
) -> UserResponse:
    user = await service.get_by_id(user_id)
    return UserResponse.model_validate(user)

