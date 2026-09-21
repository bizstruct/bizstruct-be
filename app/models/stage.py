from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid7

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from bizstruct_domain import STAGES

# from bizstruct_domain.enums import StageErrorCode, StageStatus

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project

STAGE_IDS: frozenset[str] = frozenset(
    getattr(stage, "id", stage) for stage in STAGES
)


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    

class StageErrorCode(str, Enum):
    """Error codes for stage execution failures.

    These are used to categorize and identify specific failure scenarios
    during the execution of a stage in the domain pipeline.
    """

    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"
    EXTERNAL_SERVICE_FAILURE = "external_service_failure"
    UNKNOWN_ERROR = "unknown_error"


class Stage(Base, TimestampMixin):
    """
        Represents the execution of a single domain pipeline graph step for a project.

        Domain stages and status transitions are governed by the domain package.
    """

    __tablename__ = "stages"
    __table_args__ = (
        UniqueConstraint("project_id", "type", name="uq_stages_project_id_type"),
        UniqueConstraint("id", "type", name="uq_stages_id_type"),
        CheckConstraint("retry_count >= 0", name="chk_stages_retry_count_non_negative"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid7,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    status: Mapped[StageStatus] = mapped_column(
        SAEnum(
            StageStatus,
            native_enum=False,
            length=32,
            validate_strings=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=StageStatus.PENDING,
        server_default=text(f"'{StageStatus.PENDING.value}'"),
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    error_code: Mapped[StageErrorCode | None] = mapped_column(
        SAEnum(
            StageErrorCode,
            native_enum=False,
            length=64,
            validate_strings=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=None,
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        default=None,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
    )

    project: Mapped["Project"] = relationship("Project", back_populates="stages")

    @validates("type")
    def validate_stage_type(self, key: str, value: str) -> str:
        """Validates that stage type strictly corresponds to an existing domain graph step."""
        if value not in STAGE_IDS:
            raise ValueError(f"Unknown stage type: '{value}'")
        return value

