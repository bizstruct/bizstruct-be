from collections.abc import Sequence
from uuid import UUID

from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bizstruct_domain import Stage, project_status
from bizstruct_domain import StageRow as WireRow

from app.exceptions.auth import PermissionDeniedError
from app.exceptions.base import EntityNotFoundError
from app.models.project import Project
from app.models.stage_row import StageRow
from app.schemas.project import GenerationRequest, ProjectUpdate


class ProjectService:
    """
        Service layer handling project lifecycle and ownership rules.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, project_id: UUID, current_user_id: UUID) -> Project:
        """
            Retrieves a project by ID ensuring ownership.

            Raises:
                EntityNotFoundError: If the project does not exist.
                PermissionDeniedError: If the project belongs to another user.
        """
        project = await self.session.get(Project, project_id)
        if project is None:
            raise EntityNotFoundError(entity_name="Project", identifier=str(project_id))

        if project.user_id != current_user_id:
            raise PermissionDeniedError("You do not have access to this project")

        return project

    async def list_user_projects(
        self,
        current_user_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[Project]:
        """
            Returns paginated projects belonging exclusively to the current user.
        """
        statement = (
            select(Project)
            .where(Project.user_id == current_user_id)
            .order_by(Project.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def create(self, user_id: UUID, data: GenerationRequest) -> Project:
        """
            Adds a new project owned by the specified user to the session.

            Flushes but does not commit: the caller (the generation flow) creates
            the project's first rows in the same transaction.
        """
        project = Project(
            user_id=user_id,
            title=data.resolved_title(),
            idea=data.idea,
            language=data.language,
            enabled_optional=[stage.value for stage in data.enabled_optional],
            auto_approve=data.auto_approve,
        )
        self.session.add(project)
        await self.session.flush()
        return project

    async def statuses(
        self, projects: Sequence[Project]
    ) -> dict[UUID, Literal["completed", "failed", "running"]]:
        """
            Derived status (`project_status`) of each project, from its rows.
            Reads only stage and status of the rows, not their artifacts.
        """
        result = await self.session.execute(
            select(StageRow.id, StageRow.project_id, StageRow.stage, StageRow.status)
            .where(StageRow.project_id.in_([p.id for p in projects]))
        )
        rows_by_project: dict[UUID, list[WireRow]] = {p.id: [] for p in projects}
        for row_id, project_id, stage, row_status in result.all():
            rows_by_project[project_id].append(WireRow(id=row_id, stage=stage, status=row_status))
        return {
            p.id: project_status(rows_by_project[p.id], [Stage(v) for v in p.enabled_optional])
            for p in projects
        }

    async def update(
        self,
        project_id: UUID,
        current_user_id: UUID,
        data: ProjectUpdate,
    ) -> Project:
        """
            Updates mutable project attributes after verifying ownership.

            Raises:
                EntityNotFoundError: If the project does not exist.
                PermissionDeniedError: If the user is not the owner.
        """
        project = await self.get_by_id(
            project_id=project_id,
            current_user_id=current_user_id,
        )

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(project, field, value)

        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete(self, project_id: UUID, current_user_id: UUID) -> None:
        """
            Deletes a project after verifying ownership.

            Raises:
                EntityNotFoundError: If the project does not exist.
                PermissionDeniedError: If the user is not the owner.
        """
        project = await self.get_by_id(
            project_id=project_id,
            current_user_id=current_user_id,
        )

        await self.session.delete(project)
        await self.session.commit()

