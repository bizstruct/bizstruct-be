from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid7

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bizstruct_domain import (
    STAGE_IDS,
    ArtifactRecord,
    ConsistencyReport,
    Stage,
    StageFailure,
    StageStatus,
    dependent_rows,
    is_valid_transition,
)
from bizstruct_domain import StageRow as WireRow

from app.exceptions.stage import InvalidStageTransition, StageRowNotFound
from app.models.base import utcnow
from app.models.stage_row import StageRow
from app.services.orchestration import NewRow


MAX_ERROR_MESSAGE_LENGTH = 500

_STAGE_GRAPH_ORDER: dict[Stage, int] = {stage: index for index, stage in enumerate(STAGE_IDS)}


def new_attempt_id() -> str:
    return str(uuid7())


def to_wire_row(row: StageRow) -> WireRow:
    """
        The domain's view of a stored row: what the pure domain functions
        (`ready_rows`, `dependent_rows`, `project_status`, ...) and the
        internal snapshot work on. The stored `error` (a StageFailure) is
        flattened to the wire's `error_code` and `error`.
    """
    return WireRow.model_validate(
        {
            "id": row.id,
            "stage": row.stage,
            "instance_index": row.instance_index,
            "status": row.status,
            "attempt_id": row.attempt_id,
            "refs": row.refs,
            "artifacts": row.artifacts,
            "consistency": row.consistency,
            "retry_count": row.retry_count,
            "error_code": row.error["code"] if row.error else None,
            "error": row.error["message"] if row.error else None,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }
    )


class StageService:
    """
        Owns the `stage_rows` table and every status change on it (D17, D29).

        The single place that applies the domain stage machine to rows. Receives
        the caller's session and never commits — the caller owns the
        transaction; this service may flush.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_rows(self, project_id: UUID, specs: Sequence[NewRow]) -> list[StageRow]:
        """
            Creates one `pending` row per spec, with the ids the specs carry (their
            refs already point at those ids).

            Does not check for duplicates: which rows to create, and not to
            create twice, is decided by the pure planner in
            `app.services.orchestration`, not here.
        """
        rows = [
            StageRow(
                id=spec.id,
                project_id=project_id,
                stage=spec.stage,
                instance_index=spec.instance_index,
                status=StageStatus.PENDING,
                refs={dep.value: list(ids) for dep, ids in spec.refs.items()},
                artifacts=[],
            )
            for spec in specs
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return rows

    async def get_rows(self, project_id: UUID) -> list[StageRow]:
        """
            Returns all rows of the project in domain graph order, then
            `instance_index`, then creation order (not creation order alone).
        """
        result = await self.session.execute(
            select(StageRow)
            .where(StageRow.project_id == project_id)
            .order_by(StageRow.created_at, StageRow.id)
            .execution_options(populate_existing=True)
        )
        rows = result.scalars().all()
        return sorted(rows, key=lambda row: (_STAGE_GRAPH_ORDER[row.stage], row.instance_index))

    async def get_row(self, project_id: UUID, row_id: str, lock: bool = False) -> StageRow:
        """
            Returns a single row.

            Raises:
                StageRowNotFound: If no such row exists in the project.
        """
        statement = (
            select(StageRow)
            .where(StageRow.project_id == project_id, StageRow.id == row_id)
        )
        if lock:
            # populate_existing: a row already in this session's identity map
            # may predate the lock; under the lock only the fresh state counts.
            statement = statement.with_for_update().execution_options(populate_existing=True)

        result = await self.session.execute(statement)
        row = result.scalar_one_or_none()
        if row is None:
            raise StageRowNotFound(project_id, row_id)
        return row

    async def transition(
        self,
        row: StageRow,
        target: StageStatus,
        *,
        approved: bool = False,
        failure: StageFailure | None = None,
        increment_retry: bool = False,
        reset_retry: bool = False,
    ) -> StageRow:
        """
            The single place that changes a row's status.

            Entering `running` always issues a new `attempt_id` (ADR-0011 Q4:
            every attempt of be's own gets one). Leaving for `pending` clears
            the artifacts, the consistency report and the attempt, so the row
            is as good as new (its id, and so the artifact ids derived from
            it, stay).

            Args:
                approved: Marks this transition as a user approval; only
                    then is `approved_at` set. Only meaningful when
                    `target` is `done`.
                failure: Required when `target` is `error`; stored as the
                    row's `error`, its message truncated to
                    `MAX_ERROR_MESSAGE_LENGTH`. Never raw provider or
                    stack-trace text.
                increment_retry: Increment `retry_count` by one. Only
                    meaningful when `target` is `running` (the
                    `needs_retry -> running` automatic-repair restart).
                reset_retry: Reset `retry_count` to zero. Only meaningful
                    when `target` is `running` (a user-initiated restart,
                    decision D28 — the caller is responsible for passing
                    this on `pending -> running` when the run was started
                    by the user, e.g. approve, regenerate or retry).

            Raises:
                InvalidStageTransition: If `(row.status, target)` is not
                    an allowed edge in the domain transition table.
                ValueError: If `target` is `error` without `failure`;
                    both `increment_retry` and `reset_retry` are set;
                    `approved` is set with a `target` other than `done`;
                    or `increment_retry`/`reset_retry` is set with a
                    `target` other than `running`.
        """
        current = row.status
        if not is_valid_transition(current, target):
            raise InvalidStageTransition(current, target)
        if increment_retry and reset_retry:
            raise ValueError("cannot both increment and reset retry_count in the same transition")
        if target == StageStatus.ERROR and failure is None:
            raise ValueError("failure is required when transitioning to error")
        if approved and target != StageStatus.DONE:
            raise ValueError("approved is only meaningful when target is done")
        if increment_retry and target != StageStatus.RUNNING:
            raise ValueError("increment_retry is only meaningful when target is running")
        if reset_retry and target != StageStatus.RUNNING:
            raise ValueError("reset_retry is only meaningful when target is running")

        if target == StageStatus.RUNNING:
            self._clear_attempt_fields(row)
            row.started_at = utcnow()
            row.attempt_id = new_attempt_id()
        elif target == StageStatus.PENDING:
            self._clear_attempt_fields(row)
            self._clear_result(row)
            row.attempt_id = None
        elif target in (StageStatus.AWAITING_DECISION, StageStatus.DONE, StageStatus.ERROR):
            row.finished_at = utcnow()
            if target == StageStatus.ERROR and failure is not None:
                row.error = failure.model_copy(
                    update={"message": failure.message[:MAX_ERROR_MESSAGE_LENGTH]}
                ).model_dump(mode="json")

        if approved:
            row.approved_at = utcnow()

        if increment_retry:
            row.retry_count += 1
        if reset_retry:
            row.retry_count = 0

        row.status = target
        await self.session.flush()
        return row

    async def reset_from(self, project_id: UUID, row_id: str) -> list[StageRow]:
        """
            Puts the row and every row that depends on it through `refs`
            (`dependent_rows`) back to `pending`, each through `transition`.
            Rows already `pending` are skipped. Row ids are kept, so the
            artifact ids derived from them stay valid.

            Does not touch `retry_count`: resetting it is the caller's
            responsibility on the later `pending -> running` transition
            for a user-initiated run (decision D28), not here.

            Raises:
                StageRowNotFound: If the row is not in the project.
                InvalidStageTransition: If some row cannot go back to
                    `pending` from its status. Nothing is changed for the
                    rows already reset in this call only if the caller rolls
                    back; this service never commits.
        """
        rows = await self.get_rows(project_id)
        by_id = {row.id: row for row in rows}
        if row_id not in by_id:
            raise StageRowNotFound(project_id, row_id)

        ids_to_reset = [row_id, *dependent_rows(row_id, [to_wire_row(row) for row in rows])]
        reset: list[StageRow] = []
        for current_id in ids_to_reset:
            row = await self.get_row(project_id, current_id, lock=True)
            if row.status == StageStatus.PENDING:
                continue
            reset.append(await self.transition(row, StageStatus.PENDING))
        return reset

    async def record_result(
        self,
        row: StageRow,
        artifacts: Sequence[ArtifactRecord],
        consistency: ConsistencyReport | None,
    ) -> StageRow:
        """
            Stores a result on the row, REPLACING its whole artifact set
            (ADR-0011 Q1: a regeneration may yield fewer versions, and the ones
            that are gone must go). Not a status change; the caller moves the
            row through `consistency_check` separately.
        """
        row.artifacts = [artifact.model_dump(mode="json") for artifact in artifacts]
        row.consistency = consistency.model_dump(mode="json") if consistency is not None else None
        await self.session.flush()
        return row

    async def stale_running_rows(self, project_ids: Sequence[UUID] | None, before: datetime) -> list[StageRow]:
        """
            Rows `running` since before `before`, for the lazy watchdog. With
            `project_ids` None, rows of every project.
        """
        statement = select(StageRow).where(
            StageRow.status == StageStatus.RUNNING,
            StageRow.started_at < before,
        )
        if project_ids is not None:
            statement = statement.where(StageRow.project_id.in_(project_ids))
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    def _clear_attempt_fields(row: StageRow) -> None:
        row.started_at = None
        row.finished_at = None
        row.approved_at = None
        row.error = None

    @staticmethod
    def _clear_result(row: StageRow) -> None:
        row.artifacts = []
        row.consistency = None
