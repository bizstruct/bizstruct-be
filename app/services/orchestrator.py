from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bizstruct_domain import StageErrorCode, StageStatus, ready_stages

from app.models.stage import Stage
from app.ports.queue import QueuePort
from app.services.stage import StageService

logger = structlog.get_logger(__name__)

_ACTIVE_STATUSES = (StageStatus.RUNNING, StageStatus.CONSISTENCY_CHECK)

# Arbitrary, stable namespace for advance()'s per-project advisory lock
# (pg_advisory_xact_lock(classid, objid)), so it can't collide with
# advisory locks taken elsewhere in the codebase for an unrelated purpose.
_ADVANCE_LOCK_NAMESPACE = 0x4F524348  # "ORCH" packed as bytes


class GenerationOrchestrator:
    """
        Drives stage execution: start, advance the chain, fail, cancel.

        Backed only by StageService and a QueuePort, so the run-a-project
        flow can be exercised end-to-end before ArtifactService and
        ViolationService exist (D17, D19, D26, D28, D29). Does not own a
        project's data — callers pass `project_language` per call rather
        than this class storing it.
    """

    def __init__(
        self,
        session: AsyncSession,
        stage_service: StageService,
        queue: QueuePort,
    )-> None:
        self.session = session
        self.stage_service = stage_service
        self.queue = queue

    async def run_stage(
        self,
        project_id: UUID,
        stage_type: str,
        *,
        project_language: str,
        reset_retry: bool = False,
        increment_retry: bool = False,
        comment: str | None = None,
    ) -> Stage:
        """
            Transitions `stage_type` to `running` and enqueues it for the worker.

            Commits right after the transition — enqueue_generation is
            only ever called against a committed row. If enqueueing fails,
            that commit already happened, so this compensates with a
            second, separate transition+commit to `error` /
            QUEUE_UNAVAILABLE rather than trying to roll anything back; the
            exception is logged and swallowed, since the caller has no
            transaction left to catch it in.

            Returns the stage in its final state: `running` normally, or
            `error` if the compensation path ran.
        """
        stage = await self.stage_service.get_stage(
            project_id,
            stage_type,
            lock=True,
        )
        stage = await self.stage_service.transition(
            stage, 
            StageStatus.RUNNING, 
            reset_retry=reset_retry,
            increment_retry=increment_retry,
        )
        await self.session.commit()

        try:
            await self.queue.enqueue_generation(
                project_id=project_id,
                stage_type=stage_type,
                language=project_language,
                force=increment_retry or reset_retry,
                comment=comment,
            )
        except Exception:
            logger.exception(
                "orchestrator.enqueue_generation_failed",
                project_id=str(project_id),
                stage_type=stage_type,
            )
            stage = await self.stage_service.transition(
                stage,
                StageStatus.ERROR,
                error_code=StageErrorCode.QUEUE_UNAVAILABLE,
            )
            await self.session.commit()

        return stage

    async def advance(self, project_id: UUID, *, project_language: str) -> list[Stage]:
        """
            Starts every stage that is currently ready (D17, D19).

            Idempotent: stages already running (or otherwise non-pending)
            are never ready, so calling this again before anything finishes
            starts nothing and returns [].

            Two concurrent advance() calls for the same project would
            otherwise both read the same "ready" snapshot before either
            starts anything, and both try to start it — run_stage's own
            row lock doesn't prevent this, because it's released the
            moment run_stage commits, which happens *inside* this method's
            loop, one stage at a time. So this takes a Postgres advisory
            lock keyed on project_id, on a connection of its own (not
            self.session — that connection's lock would be dropped by
            run_stage's first commit too), held for the whole method. A
            second concurrent call blocks until the first one, including
            every run_stage it started, has fully committed.

            Costs a second pool connection for the duration of the call
            (lock_conn, alongside self.session) — doubles this method's
            connection footprint under concurrency. Acceptable at this
            project's scale; would need revisiting under heavier load.
        """
        lock_params = {"ns": _ADVANCE_LOCK_NAMESPACE, "key": str(project_id)}
        engine = self.session.bind
        async with engine.connect() as lock_conn, lock_conn.begin():
            await lock_conn.execute(
                text("SELECT pg_advisory_xact_lock(:ns, hashtext(:key))"),
                lock_params,
            )

            stages = await self.stage_service.get_stages(project_id)
            ready = ready_stages(stages)
            return [
                await self.run_stage(
                    project_id,
                    stage_type,
                    project_language=project_language,
                )
                for stage_type in ready
            ]

    async def fail(
        self,
        project_id: UUID,
        stage_type: str,
        *,
        error_code: StageErrorCode,
        error: str | None = None,
    ) -> Stage:
        """
            Transitions `stage_type` straight to `error`. No queue interaction:
            there is nothing running for the worker to be told to stop.
        """
        stage = await self.stage_service.get_stage(
            project_id,
            stage_type,
            lock=True,
        )
        stage = await self.stage_service.transition(
            stage,
            StageStatus.ERROR,
            error_code=error_code,
            error=error,
        )
        await self.session.commit()
        return stage

    async def cancel(self, project_id: UUID) -> list[Stage]:
        """
            Moves every active stage (`running`, `consistency_check`) to
            `error` / CANCELED_BY_USER. Stages in `pending`, `done`,
            `awaiting_decision`, `needs_retry`, or already `error` are left
            untouched.

            `needs_retry` is deliberately excluded: nothing is running for
            it, and the domain's transition table has no `needs_retry ->
            error` edge — reaching the retry limit is not an error, the
            latest artifact goes back to the user instead (D26). The user
            resolves it through the normal retry/approve path.

            Commits the state change first (D19), then asks the worker to
            interrupt each canceled stage — cancellation requests only ever
            go out for a state that's already durable.

            Returns the stages that were canceled; [] if nothing was active.
        """
        stages = await self.stage_service.get_stages(project_id)
        active_types = [stage.type for stage in stages if stage.status in _ACTIVE_STATUSES]

        canceled: list[Stage] = []
        for stage_type in active_types:
            stage = await self.stage_service.get_stage(
                project_id,
                stage_type,
                lock=True,
            )
            canceled.append(
                await self.stage_service.transition(
                    stage,
                    StageStatus.ERROR,
                    error_code=StageErrorCode.CANCELED_BY_USER,
                )
            )
        await self.session.commit()

        for stage in canceled:
            await self.queue.request_cancellation(
                project_id=project_id,
                stage_type=stage.type,
            )

        return canceled
