from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.auth import PermissionDeniedError
from app.exceptions.base import EntityNotFoundError
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


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

    async def create(self, user_id: UUID, data: ProjectCreate) -> Project:
        """
            Creates a new project owned by the specified user.
        """
        project = Project(
            user_id=user_id,
            title=data.title,
            idea=data.idea,
            language=data.language,
            mode=data.mode,
        )
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

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

