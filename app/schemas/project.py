from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from bizstruct_domain import (
    STAGE_REGISTRY,
    ArtifactRecord,
    ConsistencyReport,
    Stage,
    StageFailure,
    StageStatus,
)

from app.models.project import Project, ProjectLanguage
from app.models.stage_row import StageRow
from app.schemas.common import CamelModel

TitleStr = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=255,
    ),
]

IdeaStr = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=50,
        max_length=2000,
    ),
]

_DEFAULT_TITLES = {
    ProjectLanguage.UK: "Новий проєкт",
    ProjectLanguage.EN: "New project",
}


def is_default_title(title: str) -> bool:
    """True for the name a project gets when its creator gave none, in any language."""
    return title in _DEFAULT_TITLES.values()


class GenerationRequest(CamelModel):
    """
        Schema for creating a project and starting its generation.
    """

    title: TitleStr | None = Field(
        default=None,
        description="Project display name; a default is used when omitted",
        examples=["My SaaS Startup"],
    )
    idea: IdeaStr = Field(
        ...,
        description="Detailed unstructured business idea description",
        examples=[
            "An automated AI-powered recruitment platform designed to screen candidates, "
            "schedule interviews, and provide predictive performance analytics for remote tech companies."
        ],
    )
    language: ProjectLanguage = Field(
        ...,
        description="Generation language (immutable once set)",
        examples=[ProjectLanguage.UK],
    )
    enabled_optional: list[Stage] = Field(
        default_factory=list,
        description="Optional stages to generate: business_case and/or environment_scan",
        examples=[[Stage.ENVIRONMENT_SCAN]],
    )
    auto_approve: bool = Field(
        default=False,
        description="Approve rows with error-level consistency violations automatically "
                    "instead of waiting for a user decision",
    )

    @field_validator("enabled_optional")
    @classmethod
    def only_generated_optional_stages(cls, value: list[Stage]) -> list[Stage]:
        """
            Keeps only optional stages that can be generated without user input, once each.

            `team_info` is user input: nothing generates it, so enabling it would
            leave every pitch waiting for data this API cannot yet submit.
        """
        for stage in value:
            if not STAGE_REGISTRY.stages[stage].is_optional:
                raise ValueError(f"'{stage.value}' is not an optional stage")
            if stage == Stage.TEAM_INFO:
                raise ValueError("'team_info' is user input and cannot be enabled until its submission exists")
        return list(dict.fromkeys(value))

    def resolved_title(self) -> str:
        return self.title or _DEFAULT_TITLES[self.language]


class ProjectUpdate(BaseModel):
    """
        Schema for updating an existing project.

        Only the title is mutable. Attempting to modify immutable fields
        such as idea, language, or status triggers a 422 extra_forbidden validation error.
    """

    model_config = ConfigDict(extra="forbid")

    title: TitleStr = Field(
        ...,
        description="Updated project title",
        examples=["Renamed SaaS Startup"],
    )


class StageRowResponse(CamelModel):
    """
        Public representation of one stage row. The artifacts, the failure and
        the consistency report are domain models and stay snake_case.
    """

    id: str = Field(..., description="Row id")
    stage: Stage = Field(..., description="The stage this row is an instance of")
    instance_index: int = Field(..., description="0-based order among rows of the same stage under the same parent")
    status: StageStatus = Field(..., description="Current status of the row")
    refs: dict[Stage, list[str]] = Field(..., description="Upstream stage -> ids of the rows this row draws from")
    attempt_id: str | None = Field(..., description="Id of the current attempt")
    retry_count: int = Field(..., description="How many retries have been counted for this row")
    error: StageFailure | None = Field(..., description="Why the row is in ERROR, if it is")
    consistency: ConsistencyReport | None = Field(..., description="The last consistency report")
    artifacts: list[ArtifactRecord] = Field(..., description="Artifacts the row produced")
    started_at: datetime | None = Field(..., description="When the current attempt started")
    finished_at: datetime | None = Field(..., description="When the row last finished")


class ProjectSummary(CamelModel):
    """
        Public representation of a project without its rows.
    """

    id: UUID = Field(..., description="Unique identifier of the project")
    title: str = Field(..., description="Project title")
    idea: str = Field(..., description="Detailed business idea")
    language: ProjectLanguage = Field(..., description="Project generation language")
    enabled_optional: list[Stage] = Field(..., description="Optional stages generated for this project")
    auto_approve: bool = Field(..., description="Whether error-level violations are approved automatically")
    status: Literal["completed", "failed", "running"] = Field(
        ...,
        description="Derived from the rows: failed if any row is in error, completed when every "
                    "expected row is done, running otherwise",
    )
    created_at: datetime = Field(..., description="Timestamp when the project was created")
    updated_at: datetime = Field(..., description="Timestamp when the project was last updated")

    @classmethod
    def build(cls, project: Project, status: Literal["completed", "failed", "running"]) -> "ProjectSummary":
        return cls.model_validate({**_project_fields(project), "status": status})


class ProjectDetail(ProjectSummary):
    """
        Public representation of a project with all its rows.
    """

    rows: list[StageRowResponse] = Field(..., description="All rows of the project")

    @classmethod
    def build(  # type: ignore[override]
        cls,
        project: Project,
        status: Literal["completed", "failed", "running"],
        rows: list[StageRow],
    ) -> "ProjectDetail":
        return cls.model_validate({**_project_fields(project), "status": status, "rows": rows})


def _project_fields(project: Project) -> dict[str, object]:
    return {
        "id": project.id,
        "title": project.title,
        "idea": project.idea,
        "language": project.language,
        "enabled_optional": project.enabled_optional,
        "auto_approve": project.auto_approve,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }
