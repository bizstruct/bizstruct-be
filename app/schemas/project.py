from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.project import ProjectLanguage, ProjectMode, ProjectStatus

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


class ProjectCreate(BaseModel):
    """
        Schema for creating a new generation project.
    """

    model_config = ConfigDict(extra="forbid")

    title: TitleStr = Field(
        ...,
        description="Project display name",
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
    mode: ProjectMode = Field(
        default=ProjectMode.PIPELINE,
        description="Generation execution mode",
        examples=[ProjectMode.PIPELINE],
    )


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


class ProjectResponse(BaseModel):
    """
        Public representation of a project.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(
        ...,
        description="Unique identifier of the project",
    )
    user_id: UUID = Field(
        ...,
        description="Owner user UUID",
    )
    title: str = Field(
        ...,
        description="Project title",
    )
    idea: str = Field(
        ...,
        description="Detailed business idea",
    )
    language: ProjectLanguage = Field(
        ...,
        description="Project generation language",
    )
    mode: ProjectMode = Field(
        ...,
        description="Project execution mode",
    )
    status: ProjectStatus = Field(
        ...,
        description="Current lifecycle state of the project",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the project was created",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the project was last updated",
    )

