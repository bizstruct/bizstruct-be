from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bizstruct_domain import STAGE_IDS, StageErrorCode, StageStatus, dependents_of, is_valid_transition

from app.exceptions.stage import InvalidStageTransition, StageNotFound, StagesAlreadyExist
from app.models.base import utcnow
from app.models.stage import Stage

# The human-readable `error` message is a short summary for the user, never
# raw provider output or a stack trace — truncated so a runaway upstream
# payload can't land in the column unbounded.
MAX_ERROR_MESSAGE_LENGTH = 500

_STAGE_GRAPH_ORDER: dict[str, int] = {stage_id: index for index, stage_id in enumerate(STAGE_IDS)}


class StageService:
    """
        Owns the `stages` table and every status change on it (D17, D29).

        Receives the caller's session and never commits — the caller owns
        the transaction; this service may flush.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_stages(self, project_id: UUID) -> list[Stage]:
        """
            Creates one stage per domain stage id, in `pending`, in domain
            graph order.

            Raises:
                StagesAlreadyExist: If the project already has stages.
        """
        existing = await self.session.execute(
            select(Stage.id).where(Stage.project_id == project_id).limit(1)
        )
        if existing.first() is not None:
            raise StagesAlreadyExist(project_id)

        stages = [
            Stage(project_id=project_id, type=stage_id, status=StageStatus.PENDING)
            for stage_id in STAGE_IDS
        ]
        self.session.add_all(stages)
        await self.session.flush()
        return stages

    async def get_stages(self, project_id: UUID) -> list[Stage]:
        """
            Returns all stages of the project in domain graph order (not
            creation order).
        """
        result = await self.session.execute(select(Stage).where(Stage.project_id == project_id))
        stages = result.scalars().all()
        return sorted(stages, key=lambda stage: _STAGE_GRAPH_ORDER[stage.type])

    async def get_stage(self, project_id: UUID, type: str, lock: bool = False) -> Stage:
        """
            Returns a single stage.

            Raises:
                StageNotFound: If no such stage exists for the project.
        """
        statement = select(Stage).where(Stage.project_id == project_id, Stage.type == type)
        if lock:
            statement = statement.with_for_update()

        result = await self.session.execute(statement)
        stage = result.scalar_one_or_none()
        if stage is None:
            raise StageNotFound(project_id, type)
        return stage

    async def transition(
        self,
        stage: Stage,
        target: StageStatus,
        *,
        approved: bool = False,
        error_code: StageErrorCode | None = None,
        error: str | None = None,
        increment_retry: bool = False,
        reset_retry: bool = False,
    ) -> Stage:
        """
            The single place that changes a stage's status.

            Args:
                approved: Marks this transition as a user approval; only
                    then is `approved_at` set.
                error_code: Required when `target` is `error`.
                error: Human-readable error summary; truncated to
                    `MAX_ERROR_MESSAGE_LENGTH` and only stored when
                    `target` is `error`. Never raw provider or
                    stack-trace text.
                increment_retry: Increment `retry_count` by one.
                reset_retry: Reset `retry_count` to zero.

            Raises:
                InvalidStageTransition: If `(stage.status, target)` is not
                    an allowed edge in the domain transition table.
                ValueError: If `target` is `error` without `error_code`,
                    or both `increment_retry` and `reset_retry` are set.
        """
        current = stage.status
        if not is_valid_transition(current, target):
            raise InvalidStageTransition(current, target)

        if increment_retry and reset_retry:
            raise ValueError("cannot both increment and reset retry_count in the same transition")

        if target == StageStatus.RUNNING:
            stage.started_at = utcnow()
            stage.finished_at = None
            stage.approved_at = None
            stage.error = None
            stage.error_code = None
        elif target == StageStatus.PENDING:
            stage.started_at = None
            stage.finished_at = None
            stage.approved_at = None
            stage.error = None
            stage.error_code = None
        elif target in (StageStatus.AWAITING_DECISION, StageStatus.DONE, StageStatus.ERROR):
            stage.finished_at = utcnow()

        if target == StageStatus.ERROR:
            if error_code is None:
                raise ValueError("error_code is required when transitioning to error")
            stage.error_code = error_code
            stage.error = error[:MAX_ERROR_MESSAGE_LENGTH] if error else None

        if approved:
            stage.approved_at = utcnow()

        if increment_retry:
            stage.retry_count += 1
        if reset_retry:
            stage.retry_count = 0

        stage.status = target
        await self.session.flush()
        return stage

    async def reset_from(self, project_id: UUID, type: str) -> list[Stage]:
        """
            Puts `type` and its transitive dependents back to `pending`,
            each through `transition`, in domain graph order. Stages
            already `pending` are skipped. Artifact versions are untouched.
        """
        stage_ids_to_reset = sorted(
            {type, *dependents_of(type)},
            key=lambda stage_id: _STAGE_GRAPH_ORDER[stage_id],
        )

        reset_stages = []
        for stage_id in stage_ids_to_reset:
            stage = await self.get_stage(project_id, stage_id)
            if stage.status == StageStatus.PENDING:
                continue
            reset_stages.append(await self.transition(stage, StageStatus.PENDING))
        return reset_stages
