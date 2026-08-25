import uuid
from datetime import datetime
from typing import Any

from bizstruct_domain.blocks.architecture import Architecture
from bizstruct_domain.blocks.empathy_map import EmpathyMap
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# ── Project ──────────────────────────────────────────────────────────────────

class ProjectCreate(CamelModel):
    title: str
    idea: str | None = None
    translation_key: str | None = None


class ProjectUpdate(CamelModel):
    title: str | None = None
    idea: str | None = None
    status: str | None = None
    translation_key: str | None = None
    models_options: dict[str, Any] | None = None
    canvas_data: dict[str, Any] | None = None
    hypotheses: dict[str, Any] | None = None
    pitch: dict[str, Any] | None = None
    scenario: dict[str, Any] | None = None
    what_if: dict[str, Any] | None = None
    architecture: Architecture | None = None
    empathy_map: EmpathyMap | None = None


class ProjectResponse(CamelModel):
    id: uuid.UUID
    title: str
    idea: str | None
    status: str
    translation_key: str | None
    models_options: dict[str, Any] | None
    canvas_data: dict[str, Any] | None
    hypotheses: dict[str, Any] | None
    pitch: dict[str, Any] | None
    scenario: dict[str, Any] | None
    what_if: dict[str, Any] | None
    # Sourced from bizstruct_domain — pilot slice, other blocks stay dict[str, Any]
    # until they get their own domain models. Note this model has no camelCase
    # alias_generator of its own, so its fields serialize snake_case even though
    # every sibling field here is camelCased.
    architecture: Architecture | None
    empathy_map: EmpathyMap | None
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(CamelModel):
    id: uuid.UUID
    title: str
    idea: str | None
    status: str
    translation_key: str | None
    created_at: datetime
    updated_at: datetime


# ── Canvas (example nested block schema) ─────────────────────────────────────

class CanvasBlock(CamelModel):
    key_partners: list[str] | None = None
    key_activities: list[str] | None = None
    key_resources: list[str] | None = None
    value_propositions: list[str] | None = None
    customer_relationships: list[str] | None = None
    channels: list[str] | None = None
    customer_segments: list[str] | None = None
    cost_structure: list[str] | None = None
    revenue_streams: list[str] | None = None


class CanvasResponse(CamelModel):
    project_id: uuid.UUID
    canvas_data: CanvasBlock | None
