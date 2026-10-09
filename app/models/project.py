from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid7

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.stage_row import StageRow


class ProjectLanguage(StrEnum):
    UK = "uk"
    EN = "en"


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid7,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    idea: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    language: Mapped[ProjectLanguage] = mapped_column(
        SAEnum(
            ProjectLanguage,
            native_enum=False,
            length=32,
            validate_strings=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    enabled_optional: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    auto_approve: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="projects",
    )
    rows: Mapped[list["StageRow"]] = relationship(
        "StageRow",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="StageRow.created_at",
    )
