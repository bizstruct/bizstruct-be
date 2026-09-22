from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid7

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.stage import Stage


class ProjectLanguage(StrEnum):
    UK = "uk"
    EN = "en"


class ProjectMode(StrEnum):
    STEPWISE = "stepwise"
    AGENT = "agent"


class ProjectStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    AWAITING_DECISION = "awaiting_decision"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"


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
    mode: Mapped[ProjectMode] = mapped_column(
        SAEnum(
            ProjectMode,
            native_enum=False,
            length=32,
            validate_strings=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ProjectMode.STEPWISE,
        nullable=False,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(
            ProjectStatus,
            native_enum=False,
            length=32,
            validate_strings=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ProjectStatus.PENDING,
        nullable=False,
    )
    consistency_loop: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="projects",
    )
    stages: Mapped[list["Stage"]] = relationship(
        "Stage",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Stage.created_at",
    )

