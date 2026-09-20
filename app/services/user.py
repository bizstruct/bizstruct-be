from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.exceptions.base import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
)
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise EntityNotFoundError(entity_name="User", identifier=str(user_id))
        return user

    async def get_by_email(self, email: str) -> User | None:
        query = select(User).where(User.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_users(self, skip: int = 0, limit: int = 50) -> Sequence[User]:
        query = select(User).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create(self, data: UserCreate) -> User:
        await self._ensure_email_is_unique(data.email)

        user = User(
            email=data.email,
            full_name=data.full_name,
            password_hash=hash_password(data.password),
            is_service=data.is_service,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user_id: UUID, data: UserUpdate) -> User:
        user = await self.get_by_id(user_id)
        update_dict = data.model_dump(exclude_unset=True)

        if "email" in update_dict and update_dict["email"] != user.email:
            await self._ensure_email_is_unique(
                update_dict["email"], exclude_user_id=user.id
            )

        if "password" in update_dict:
            plain_password = update_dict.pop("password")
            if plain_password:
                user.password_hash = hash_password(plain_password)

        for key, value in update_dict.items():
            setattr(user, key, value)

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def _ensure_email_is_unique(
        self, email: str, exclude_user_id: UUID | None = None
    ) -> None:
        existing_user = await self.get_by_email(email)
        if existing_user is None:
            return

        if exclude_user_id is not None and existing_user.id == exclude_user_id:
            return

        raise EntityAlreadyExistsError(
            entity_name="User",
            field="email",
            value=email,
        )

