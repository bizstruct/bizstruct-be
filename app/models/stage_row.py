from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid7

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bizstruct_domain import Stage, StageStatus

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project


def _new_row_id() -> str:
    return str(uuid7())


class StageRow(Base, TimestampMixin):
    """
        One row of the stage graph for a project (ADR-0011).

        A stage can have several rows (one empathy_map per segment, one canvas
        per Patterns group, ...), so there is deliberately no uniqueness on
        (project_id, stage). `refs` records which rows this row draws its
        input from; `artifacts` holds what the row produced, as ArtifactRecord
        dumps. Statuses change only through StageService.
    """

    __tablename__ = "stage_rows"
    __table_args__ = (
        Index("ix_stage_rows_project_id_stage_instance_index", "project_id", "stage", "instance_index"),
        CheckConstraint("retry_count >= 0", name="chk_stage_rows_retry_count_non_negative"),
        CheckConstraint("instance_index >= 0", name="chk_stage_rows_instance_index_non_negative"),
    )

    # The wire contract carries row ids as strings (ADR-0011), so the primary
    # key is a string holding a uuid rather than a native uuid.
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_row_id,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage: Mapped[Stage] = mapped_column(
        SAEnum(
            Stage,
            native_enum=False,
            length=32,
            validate_strings=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    instance_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
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
    refs: Mapped[dict[str, list[str]]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    attempt_id: Mapped[str | None] = mapped_column(
        String(64),
        default=None,
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    error: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        default=None,
        nullable=True,
    )
    consistency: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        default=None,
        nullable=True,
    )
    artifacts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
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

    project: Mapped["Project"] = relationship("Project", back_populates="rows")
