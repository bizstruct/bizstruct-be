from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Literal
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bizstruct_domain import (
    ArtifactType,
    QueueMessage,
    RowTarget,
    Stage,
    StageAction,
    StageErrorCode,
    StageEvent,
    StageFailure,
    StageResult,
    StageStatus,
    available_actions,
    ready_rows,
)

from app.exceptions.base import EntityNotFoundError
from app.exceptions.stage import StageActionNotAllowed, StaleAttempt
from app.models.base import utcnow
from app.models.project import Project
from app.models.stage_row import StageRow
from app.ports.events import EventPort
from app.ports.queue import QueuePort
from app.schemas.project import is_default_title
from app.services.orchestration import (
    IdFactory,
    default_row_id,
    expand_rows,
    initial_rows,
    is_stuck,
    result_problems,
    success_path,
)
from app.services.stage import StageService, to_wire_row

logger = structlog.get_logger(__name__)

_ACTIVE_STATUSES = (StageStatus.RUNNING, StageStatus.CONSISTENCY_CHECK)

# Statuses a row is in after its result has been applied; a repeat of the same
# attempt's result is then a duplicate, not a stale attempt (ADR-0011 Q4).
_APPLIED_STATUSES = (StageStatus.DONE, StageStatus.AWAITING_DECISION)


@dataclass
class ApplyOutcome:
    """What `apply_result` did: applied, a duplicate of an applied result, or invalid (row now ERROR)."""

    kind: Literal["applied", "duplicate", "invalid"]
    problems: list[str] = field(default_factory=list)


@dataclass
class _Work:
    """What a unit of work announces once its transaction has committed."""

    events: list[StageEvent] = field(default_factory=list)
    messages: list[QueueMessage] = field(default_factory=list)


class GenerationOrchestrator:
    """
        Drives stage execution over rows: start a project, apply results,
        advance the graph, regenerate, approve, fail, cancel.

        Backed by StageService (the only place statuses change), the pure
        planner in `app.services.orchestration`, a QueuePort and an EventPort,
        so a whole run can be exercised without Azure (D17, D19, D26, D28, D29).

        Every operation is one transaction: it locks the project row (so two
        results of the same project never expand or advance concurrently),
        changes rows, commits once, and only then publishes events and
        enqueues messages — signals only ever go out for state that is durable.
    """

    def __init__(
        self,
        session: AsyncSession,
        stage_service: StageService,
        queue: QueuePort,
        events: EventPort | None = None,
        *,
        stuck_timeout_seconds: int = 1800,
        new_row_id: IdFactory = default_row_id,
    ) -> None:
        self.session = session
        self.stage_service = stage_service
        self.queue = queue
        self.events = events
        self.stuck_timeout_seconds = stuck_timeout_seconds
        self.new_row_id = new_row_id

    # ------------------------------------------------------------------ operations

    async def start(self, project: Project) -> None:
        """
            Creates the first rows of a freshly added project (the brief and the
            enabled optional stages that take it) and starts every row that is
            ready. The project must already be added to the session; commits.
        """
        work = _Work()
        await self.session.flush()
        specs = initial_rows(self._enabled(project), self.new_row_id)
        rows = await self.stage_service.create_rows(project.id, specs)
        work.events += [self._event(row, StageStatus.PENDING) for row in rows]
        await self._advance(work, project)
        await self._commit_and_dispatch(work, project)

    async def apply_result(self, project_id: UUID | str, result: StageResult) -> ApplyOutcome:
        """
            Applies ml's result for a row (the hook, ADR-0011 Q4, Q7, Q9).

            `failed` -> ERROR with the failure. `success` -> the artifacts are
            validated; invalid ones move the row to ERROR (generation_failed) and
            return `invalid` (the caller answers 422); valid ones are stored
            (replacing the row's previous set) and the row walks
            RUNNING -> CONSISTENCY_CHECK -> DONE | AWAITING_DECISION (-> DONE at
            once for an auto-approve project). Then the newly knowable rows are
            created and the ready ones started, all in the same transaction.

            Raises:
                EntityNotFoundError: Unknown project (404).
                StageRowNotFound: Unknown row (404).
                StaleAttempt: The row is not RUNNING or belongs to another
                    attempt (409). A repeat of an applied result is a duplicate
                    and changes nothing.
        """
        project = await self._lock_project(project_id)
        row = await self.stage_service.get_row(project.id, result.stage_row_id, lock=True)

        if row.status in _APPLIED_STATUSES and row.attempt_id == result.attempt_id:
            return ApplyOutcome("duplicate")
        if row.status != StageStatus.RUNNING or row.attempt_id != result.attempt_id:
            raise StaleAttempt(row.id, row.status)

        work = _Work()
        if result.status == "failed":
            assert result.error is not None  # guaranteed by StageResult
            await self._move(work, row, StageStatus.ERROR, failure=result.error)
            await self._commit_and_dispatch(work, project)
            return ApplyOutcome("applied")

        wire_rows = [to_wire_row(r) for r in await self.stage_service.get_rows(project.id)]
        problems = result_problems(to_wire_row(row), result, wire_rows)
        if problems:
            failure = StageFailure(code=StageErrorCode.GENERATION_FAILED, message="; ".join(problems))
            await self._move(work, row, StageStatus.ERROR, failure=failure)
            await self._commit_and_dispatch(work, project)
            return ApplyOutcome("invalid", problems)

        await self.stage_service.record_result(row, result.artifacts, result.consistency)
        self._name_project_from_brief(project, row, result)
        for target in success_path(result.consistency, project.auto_approve):
            await self._move(work, row, target, approved=target == StageStatus.DONE and row.status == StageStatus.AWAITING_DECISION)
        await self._grow_and_advance(work, project)
        await self._commit_and_dispatch(work, project)
        return ApplyOutcome("applied")

    async def advance(self, project_id: UUID) -> None:
        """
            Starts every row that is currently ready (D17, D19).

            Idempotent: rows already running (or otherwise non-pending) are never
            ready, so calling this again before anything finishes starts nothing.
        """
        project = await self._lock_project(project_id)
        work = _Work()
        await self._advance(work, project)
        await self._commit_and_dispatch(work, project)

    async def regenerate(self, project_id: UUID, row_id: str) -> None:
        """
            User regeneration (or retry of an ERROR row): the row and every row
            that depends on it go back to PENDING with their artifacts cleared
            (row ids stay, so derived artifact ids stay valid), then whatever is
            ready starts.

            Raises:
                StageRowNotFound: Unknown row (404).
                StageActionNotAllowed: The stage machine offers neither
                    regenerate nor retry in the row's status (409).
                InvalidStageTransition: A dependent row cannot go back to
                    pending from its status (409); nothing is changed.
        """
        project = await self._lock_project(project_id)
        row = await self.stage_service.get_row(project.id, row_id, lock=True)
        offered = available_actions(row.status)
        if StageAction.REGENERATE not in offered and StageAction.RETRY not in offered:
            raise StageActionNotAllowed("regenerate", row.id, row.status)

        work = _Work()
        for reset in await self.stage_service.reset_from(project.id, row.id):
            work.events.append(self._event(reset, StageStatus.PENDING))
        await self._advance(work, project)
        await self._commit_and_dispatch(work, project)

    async def approve(self, project_id: UUID, row_id: str) -> None:
        """
            User approval of a row awaiting a decision: AWAITING_DECISION -> DONE,
            keeping the consistency report. Then newly knowable rows are created
            and ready ones started.

            Raises:
                StageRowNotFound: Unknown row (404).
                StageActionNotAllowed: The row is not awaiting a decision (409).
        """
        project = await self._lock_project(project_id)
        row = await self.stage_service.get_row(project.id, row_id, lock=True)
        if StageAction.APPROVE not in available_actions(row.status):
            raise StageActionNotAllowed("approve", row.id, row.status)

        work = _Work()
        await self._move(work, row, StageStatus.DONE, approved=True)
        await self._grow_and_advance(work, project)
        await self._commit_and_dispatch(work, project)

    async def fail(self, project_id: UUID, row_id: str, failure: StageFailure) -> StageRow:
        """
            Transitions a row straight to `error`. No queue interaction:
            there is nothing running for the worker to be told to stop.
        """
        project = await self._lock_project(project_id)
        row = await self.stage_service.get_row(project.id, row_id, lock=True)
        work = _Work()
        await self._move(work, row, StageStatus.ERROR, failure=failure)
        await self._commit_and_dispatch(work, project)
        return row

    async def cancel(self, project_id: UUID) -> list[StageRow]:
        """
            Moves every active row (`running`, `consistency_check`) to
            `error` / CANCELED_BY_USER. Rows in `pending`, `done`,
            `awaiting_decision`, `needs_retry`, or already `error` are left
            untouched.

            `needs_retry` is deliberately excluded: nothing is running for
            it, and the domain's transition table has no `needs_retry ->
            error` edge — reaching the retry limit is not an error, the
            latest artifact goes back to the user instead (D26). The user
            resolves it through the normal retry/approve path.

            Commits the state change first (D19), then asks the worker to
            interrupt each canceled row — cancellation requests only ever
            go out for a state that's already durable.

            Returns the rows that were canceled; [] if nothing was active.
        """
        project = await self._lock_project(project_id)
        work = _Work()
        canceled: list[StageRow] = []
        for row in await self.stage_service.get_rows(project.id):
            if row.status in _ACTIVE_STATUSES:
                failure = StageFailure(code=StageErrorCode.CANCELED_BY_USER, message="Canceled by the user.")
                canceled.append(await self._move(work, row, StageStatus.ERROR, failure=failure))
        await self._commit_and_dispatch(work, project)

        for row in canceled:
            await self.queue.request_cancellation(project_id=str(project.id), stage_row_id=row.id)
        return canceled

    async def expire_stuck(self, project_ids: Sequence[UUID] | None = None) -> None:
        """
            The lazy watchdog: rows RUNNING for longer than the stuck timeout
            become ERROR (stuck_timeout). Called when projects are read; there is
            no background worker. With `project_ids` None, checks every project.
        """
        cutoff = utcnow() - timedelta(seconds=self.stuck_timeout_seconds)
        stale = await self.stage_service.stale_running_rows(project_ids, cutoff)
        for project_id in dict.fromkeys(row.project_id for row in stale):
            project = await self._lock_project(project_id)
            work = _Work()
            now = utcnow()
            for row in await self.stage_service.get_rows(project.id):
                if row.status == StageStatus.RUNNING and is_stuck(row.started_at, now, self.stuck_timeout_seconds):
                    failure = StageFailure(
                        code=StageErrorCode.STUCK_TIMEOUT,
                        message=f"No result within {self.stuck_timeout_seconds} seconds.",
                    )
                    await self._move(work, row, StageStatus.ERROR, failure=failure)
            await self._commit_and_dispatch(work, project)

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _name_project_from_brief(project: Project, row: StageRow, result: StageResult) -> None:
        """
            Replaces the default project name with the one the brief proposes. A name the
            user chose (at creation or by renaming) is never touched, so regenerating the
            brief does not undo a rename.
        """
        if row.stage != Stage.BRIEF or not is_default_title(project.title):
            return
        for artifact in result.artifacts:
            title = str(artifact.data.get("project_title") or "").strip()
            if artifact.type == ArtifactType.BRIEF and title:
                project.title = title
                return

    @staticmethod
    def _enabled(project: Project) -> list[Stage]:
        return [Stage(value) for value in project.enabled_optional]

    @staticmethod
    def _event(row: StageRow, status: StageStatus) -> StageEvent:
        return StageEvent(project_id=str(row.project_id), stage_row_id=row.id, stage=row.stage, status=status)

    async def _lock_project(self, project_id: UUID | str) -> Project:
        """
            Locks the project row for the rest of the transaction, serialising every
            operation on one project. Fresh state: the identity map is refreshed.
        """
        try:
            key = project_id if isinstance(project_id, UUID) else UUID(project_id)
        except ValueError:
            raise EntityNotFoundError(entity_name="Project", identifier=str(project_id)) from None
        result = await self.session.execute(
            select(Project)
            .where(Project.id == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise EntityNotFoundError(entity_name="Project", identifier=str(key))
        return project

    async def _move(
        self,
        work: _Work,
        row: StageRow,
        target: StageStatus,
        *,
        approved: bool = False,
        failure: StageFailure | None = None,
    ) -> StageRow:
        """One transition through StageService, remembered for the event to publish after commit."""
        await self.stage_service.transition(row, target, approved=approved, failure=failure)
        work.events.append(self._event(row, target))
        return row

    async def _grow_and_advance(self, work: _Work, project: Project) -> None:
        rows = [to_wire_row(r) for r in await self.stage_service.get_rows(project.id)]
        specs = expand_rows(rows, self._enabled(project), self.new_row_id)
        created = await self.stage_service.create_rows(project.id, specs)
        work.events += [self._event(row, StageStatus.PENDING) for row in created]
        await self._advance(work, project)

    async def _advance(self, work: _Work, project: Project) -> None:
        """Moves every ready row to RUNNING (new attempt) and queues one message per row."""
        rows = await self.stage_service.get_rows(project.id)
        by_id = {row.id: row for row in rows}
        ready = ready_rows([to_wire_row(r) for r in rows], self._enabled(project))
        for row_id in ready:
            row = await self._move(work, by_id[row_id], StageStatus.RUNNING)
            assert row.attempt_id is not None
            work.messages.append(
                QueueMessage(
                    project_id=str(project.id),
                    language=project.language.value,
                    targets=[RowTarget(stage_row_id=row.id, stage=row.stage, attempt_id=row.attempt_id)],
                )
            )

    async def _commit_and_dispatch(self, work: _Work, project: Project) -> None:
        """
            Commits, then publishes the events and enqueues the messages.

            If enqueueing fails, the transition to `running` already committed,
            so this compensates with a second, separate transition+commit to
            `error` / QUEUE_UNAVAILABLE rather than trying to roll anything
            back; the exception is logged and swallowed, since the caller has no
            transaction left to catch it in.
        """
        await self.session.commit()
        await self._publish(work.events)

        for message in work.messages:
            target = message.targets[0]
            try:
                await self.queue.enqueue(message)
            except Exception:
                logger.exception(
                    "orchestrator.enqueue_failed",
                    project_id=message.project_id,
                    stage=target.stage.value,
                    stage_row_id=target.stage_row_id,
                )
                row = await self.stage_service.get_row(project.id, target.stage_row_id, lock=True)
                if row.status == StageStatus.RUNNING and row.attempt_id == target.attempt_id:
                    failed = _Work()
                    failure = StageFailure(code=StageErrorCode.QUEUE_UNAVAILABLE, message="The generation queue is unavailable.")
                    await self._move(failed, row, StageStatus.ERROR, failure=failure)
                    await self.session.commit()
                    await self._publish(failed.events)
                else:
                    # Nothing to change; commit (not rollback, which would expire every
                    # loaded object) only to release the row lock taken above.
                    await self.session.commit()

    async def _publish(self, events: Sequence[StageEvent]) -> None:
        if self.events is None:
            return
        for event in events:
            try:
                await self.events.publish(event)
            except Exception:
                logger.exception("orchestrator.publish_failed", stage_row_id=event.stage_row_id)
