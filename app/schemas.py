import uuid
from datetime import datetime

from bizstruct_domain.blocks.architecture import Architecture
from bizstruct_domain.blocks.empathy_map import EmpathyMap
from bizstruct_domain.blocks.scenario import Scenario
from bizstruct_domain.blocks.pitch import Pitch
from bizstruct_domain.blocks.hypotheses import Hypotheses
from bizstruct_domain.blocks.models_options import ModelsOptions
from bizstruct_domain.blocks.canvas import Canvas
from bizstruct_domain.blocks.what_if import WhatIf
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


# ── Project ──────────────────────────────────────────────────────────────────

class ProjectCreate(CamelModel):
    title: str
    idea: str | None = None
    translation_key: str | None = None
    # Generation language ("uk"/"en"), fixed for the whole project. Not
    # translation_key (that's an unrelated frontend i18n lookup key).
    language: str = "en"


class ProjectUpdate(CamelModel):
    title: str | None = None
    idea: str | None = None
    status: str | None = None
    translation_key: str | None = None
    language: str | None = None
    models_options: ModelsOptions | None = None
    # Canvas, not CanvasGenerated — a PATCH here is either a full CRUD
    # replace or comes from bizstruct-ml's hook (see internal.py), and CRUD
    # edits aren't bound by the 2-4-cards-per-section generation rule (see
    # bizstruct_domain.blocks.canvas's module docstring).
    canvas: Canvas | None = None
    what_if: WhatIf | None = None
    architecture: Architecture | None = None
    empathy_map: EmpathyMap | None = None
    scenario: Scenario | None = None
    pitch: Pitch | None = None
    hypotheses: Hypotheses | None = None


class ProjectResponse(CamelModel):
    id: uuid.UUID
    title: str
    idea: str | None
    status: str
    translation_key: str | None
    language: str
    models_options: ModelsOptions | None
    canvas: Canvas | None
    what_if: WhatIf | None
    # Sourced from bizstruct_domain — pilot slice, other blocks stay dict[str, Any]
    # until they get their own domain models. Note this model has no camelCase
    # alias_generator of its own, so its fields serialize snake_case even though
    # every sibling field here is camelCased.
    architecture: Architecture | None
    empathy_map: EmpathyMap | None
    scenario: Scenario | None
    pitch: Pitch | None
    hypotheses: Hypotheses | None
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(CamelModel):
    id: uuid.UUID
    title: str
    idea: str | None
    status: str
    translation_key: str | None
    language: str
    created_at: datetime
    updated_at: datetime

