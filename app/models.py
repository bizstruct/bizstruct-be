import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    idea: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="generating")
    translation_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # AI-generated business model blocks
    models_options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    canvas: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    empathy_map: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    hypotheses: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pitch: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scenario: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    what_if: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    architecture: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
