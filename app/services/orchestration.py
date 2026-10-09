"""Pure orchestration rules for the stage-row pipeline (ADR-0011).

Decides WHICH rows exist, WHICH are valid results and WHICH transitions follow
a successful result. No FastAPI, no database, no queue: the functions take
and return domain values (`bizstruct_domain.StageRow` and friends), so they can
be unit-tested with plain objects. `GenerationOrchestrator` does the
persistence around them. The graph rules themselves (`ready_rows`,
`dependent_rows`, `validate_row_refs`, ...) are the domain's and are used, never
re-implemented, here.
"""

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid7

from pydantic import ValidationError

from bizstruct_domain import (
    ARTIFACT_HOLDERS,
    ARTIFACT_STAGE,
    MAX_SEGMENTS,
    ArtifactRecord,
    ArtifactType,
    Brief,
    ConsistencyReport,
    Patterns,
    Stage,
    StageResult,
    StageStatus,
    canvas_rows_for,
    parse_artifact,
    row_of_artifact,
    validate_row_refs,
)
from bizstruct_domain import StageRow as WireRow

IdFactory = Callable[[], str]


def default_row_id() -> str:
    return str(uuid7())


@dataclass(frozen=True)
class NewRow:
    """A row the planner wants created, `pending`. `id` is assigned here so refs can point at it."""

    id: str
    stage: Stage
    instance_index: int
    refs: dict[Stage, list[str]]


class _Plan:
    """Rows to create, with a working view (existing + planned) later steps can reference."""

    def __init__(self, rows: Sequence[WireRow], new_id: IdFactory) -> None:
        self.work: list[WireRow] = list(rows)
        self.created: list[NewRow] = []
        self._new_id = new_id

    def add(self, stage: Stage, instance_index: int, refs: dict[Stage, list[str]]) -> WireRow:
        validate_row_refs(stage, refs)
        row_id = self._new_id()
        self.created.append(NewRow(id=row_id, stage=stage, instance_index=instance_index, refs=refs))
        wire = WireRow(id=row_id, stage=stage, instance_index=instance_index, status=StageStatus.PENDING, refs=refs)
        self.work.append(wire)
        return wire

    def of_stage(self, stage: Stage) -> list[WireRow]:
        return sorted((r for r in self.work if r.stage == stage), key=lambda r: r.instance_index)

    def with_ref(self, stage: Stage, dep: Stage, row_id: str) -> WireRow | None:
        """The row of `stage` that draws from exactly `[row_id]` for `dep`, if any."""
        for row in self.work:
            if row.stage == stage and row.refs.get(dep) == [row_id]:
                return row
        return None


def initial_rows(enabled_optional: Collection[Stage], new_id: IdFactory = default_row_id) -> list[NewRow]:
    """The rows a new project starts with: `brief`, plus the ENABLED optional stages
    that take the brief (business_case, environment_scan). `team_info` is user input
    and is never created here."""
    plan = _Plan([], new_id)
    brief = plan.add(Stage.BRIEF, 0, {})
    for stage in (Stage.BUSINESS_CASE, Stage.ENVIRONMENT_SCAN):
        if stage in enabled_optional:
            plan.add(stage, 0, {Stage.BRIEF: [brief.id]})
    return plan.created


def _artifact(row: WireRow, artifact_type: ArtifactType) -> ArtifactRecord:
    for record in row.artifacts:
        if record.type == artifact_type:
            return record
    raise ValueError(f"row '{row.id}' ({row.stage.value}) is done but holds no '{artifact_type.value}' artifact")


def _expand_after_brief(plan: _Plan, brief_row: WireRow) -> None:
    brief = parse_artifact(_artifact(brief_row, ArtifactType.BRIEF))
    assert isinstance(brief, Brief)
    candidates = brief.customer_segment_candidates[:MAX_SEGMENTS]

    have = {row.instance_index for row in plan.work if row.stage == Stage.EMPATHY_MAP and row.refs.get(Stage.BRIEF) == [brief_row.id]}
    for k in range(len(candidates)):
        if k not in have:
            plan.add(Stage.EMPATHY_MAP, k, {Stage.BRIEF: [brief_row.id]})

    for empathy in plan.of_stage(Stage.EMPATHY_MAP):
        for stage in (Stage.CUSTOMER_SCENARIO, Stage.IDEATION):
            if plan.with_ref(stage, Stage.EMPATHY_MAP, empathy.id) is None:
                plan.add(stage, 0, {Stage.EMPATHY_MAP: [empathy.id]})

    if not plan.of_stage(Stage.PATTERNS):
        plan.add(
            Stage.PATTERNS,
            0,
            {
                Stage.CUSTOMER_SCENARIO: [r.id for r in plan.of_stage(Stage.CUSTOMER_SCENARIO)],
                Stage.IDEATION: [r.id for r in plan.of_stage(Stage.IDEATION)],
            },
        )


def _expand_after_patterns(plan: _Plan, patterns_row: WireRow) -> None:
    patterns = parse_artifact(_artifact(patterns_row, ArtifactType.PATTERNS))
    assert isinstance(patterns, Patterns)
    (brief_row,) = plan.of_stage(Stage.BRIEF)

    have = {row.instance_index for row in plan.work if row.stage == Stage.CANVAS and row.refs.get(Stage.PATTERNS) == [patterns_row.id]}
    for position, spec in enumerate(canvas_rows_for(patterns)):
        if position in have:
            continue
        empathy_rows: list[WireRow] = []
        for empathy_id in spec.empathy_map_ids:
            holder = row_of_artifact(plan.work, empathy_id)
            if holder is None or holder.stage != Stage.EMPATHY_MAP:
                raise ValueError(f"group '{spec.group_id}' names empathy map '{empathy_id}', which no empathy_map row holds")
            empathy_rows.append(holder)
        refs: dict[Stage, list[str]] = {
            Stage.BRIEF: [brief_row.id],
            Stage.EMPATHY_MAP: [r.id for r in empathy_rows],
            Stage.CUSTOMER_SCENARIO: [],
            Stage.IDEATION: [],
            Stage.PATTERNS: [patterns_row.id],
        }
        for empathy in empathy_rows:
            for stage in (Stage.CUSTOMER_SCENARIO, Stage.IDEATION):
                refs[stage] += [r.id for r in plan.work if r.stage == stage and r.refs.get(Stage.EMPATHY_MAP) == [empathy.id]]
        plan.add(Stage.CANVAS, position, refs)


def _expand_after_canvas(plan: _Plan, canvas_row: WireRow, enabled_optional: Collection[Stage]) -> None:
    def shared(stage: Stage) -> list[str]:
        if stage not in enabled_optional:
            return []
        return [r.id for r in plan.of_stage(stage)][:1]

    cycle = plan.with_ref(Stage.SWOT_ERRC_CYCLE, Stage.CANVAS, canvas_row.id)
    if cycle is None:
        refs: dict[Stage, list[str]] = {Stage.CANVAS: [canvas_row.id]}
        if scan := shared(Stage.ENVIRONMENT_SCAN):
            refs[Stage.ENVIRONMENT_SCAN] = scan
        cycle = plan.add(Stage.SWOT_ERRC_CYCLE, 0, refs)

    storytelling = plan.with_ref(Stage.STORYTELLING, Stage.SWOT_ERRC_CYCLE, cycle.id)
    if storytelling is None:
        storytelling = plan.add(Stage.STORYTELLING, 0, {Stage.SWOT_ERRC_CYCLE: [cycle.id]})
    if plan.with_ref(Stage.FUTURE_SCENARIO, Stage.SWOT_ERRC_CYCLE, cycle.id) is None:
        plan.add(Stage.FUTURE_SCENARIO, 0, {Stage.SWOT_ERRC_CYCLE: [cycle.id]})
    if plan.with_ref(Stage.PITCH, Stage.STORYTELLING, storytelling.id) is None:
        refs = {Stage.STORYTELLING: [storytelling.id], Stage.SWOT_ERRC_CYCLE: [cycle.id]}
        for stage in (Stage.TEAM_INFO, Stage.BUSINESS_CASE):
            if ids := shared(stage):
                refs[stage] = ids
        plan.add(Stage.PITCH, 0, refs)


def expand_rows(
    rows: Sequence[WireRow],
    enabled_optional: Collection[Stage] = (),
    new_id: IdFactory = default_row_id,
) -> list[NewRow]:
    """The rows that became knowable because some rows are DONE, and do not exist yet.

    Idempotent: it looks at what exists (by `refs` and `instance_index`) and
    returns only what is missing, so running it after every result never creates
    a row twice. brief DONE -> empathy_map per segment candidate (at most
    MAX_SEGMENTS), a customer_scenario and an ideation per map, and the patterns
    row; patterns DONE -> a canvas row per group; canvas DONE -> its
    swot_errc_cycle, storytelling, future_scenario and pitch rows. Every row's
    refs are checked with `validate_row_refs`.

    Raises:
        ValueError: If a DONE row holds no artifact, or a Patterns group names an
            empathy map no row holds. `result_problems` rejects the latter before
            a Patterns result is applied, so it signals corrupt stored data here.
    """
    plan = _Plan(rows, new_id)
    for row in [r for r in rows if r.stage == Stage.BRIEF and r.status == StageStatus.DONE]:
        _expand_after_brief(plan, row)
    for row in [r for r in rows if r.stage == Stage.PATTERNS and r.status == StageStatus.DONE]:
        _expand_after_patterns(plan, row)
    for row in [r for r in rows if r.stage == Stage.CANVAS and r.status == StageStatus.DONE]:
        _expand_after_canvas(plan, row, enabled_optional)
    return plan.created


def _summarize(error: ValueError) -> str:
    if isinstance(error, ValidationError):
        return "; ".join(f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in error.errors()[:5])
    return str(error)


def result_problems(row: WireRow, result: StageResult, rows: Sequence[WireRow]) -> list[str]:
    """Why a successful `result` cannot be stored on `row`; empty when it can.

    Checks, per artifact, that the type may live in this row's stage
    (`ARTIFACT_HOLDERS`), that the id is unique, that `data` validates against the
    type's persisted model and that the record id equals the artifact's own id
    (`parse_artifact`); that the row holds at least one artifact of its own stage;
    and, for `patterns`, that every empathy map a group names is held by a row of
    the project (otherwise no canvas row could be built).
    """
    problems: list[str] = []
    seen: set[str] = set()
    parsed: dict[str, object] = {}
    for record in result.artifacts:
        label = f"{record.type.value} '{record.id}'"
        if row.stage not in ARTIFACT_HOLDERS[record.type]:
            problems.append(f"{label}: a {row.stage.value} row cannot hold a {record.type.value}")
            continue
        if record.id in seen:
            problems.append(f"{label}: duplicate artifact id")
            continue
        seen.add(record.id)
        try:
            parsed[record.id] = parse_artifact(record)
        except ValueError as error:
            problems.append(f"{label}: {_summarize(error)}")

    if not problems and not any(ARTIFACT_STAGE[r.type] == row.stage for r in result.artifacts):
        problems.append(f"{row.stage.value} row returned none of its own artifacts")

    if row.stage == Stage.PATTERNS:
        for record in result.artifacts:
            patterns = parsed.get(record.id)
            if not isinstance(patterns, Patterns):
                continue
            for spec in canvas_rows_for(patterns):
                for empathy_id in spec.empathy_map_ids:
                    holder = row_of_artifact(rows, empathy_id)
                    if holder is None or holder.stage != Stage.EMPATHY_MAP:
                        problems.append(f"patterns group '{spec.group_id}' names empathy map '{empathy_id}', which no row holds")
    return problems


def success_path(report: ConsistencyReport | None, auto_approve: bool) -> tuple[StageStatus, ...]:
    """The statuses a RUNNING row passes through after a successful result, in order.

    `RUNNING -> CONSISTENCY_CHECK -> DONE`, or, with an error-level violation,
    `-> AWAITING_DECISION`; with `auto_approve` that is followed at once by the
    user's approve (`AWAITING_DECISION -> DONE`). The report is kept either way.
    """
    if report is not None and report.has_errors:
        path = (StageStatus.CONSISTENCY_CHECK, StageStatus.AWAITING_DECISION)
        return (*path, StageStatus.DONE) if auto_approve else path
    return (StageStatus.CONSISTENCY_CHECK, StageStatus.DONE)


def is_stuck(started_at: datetime | None, now: datetime, timeout_seconds: int) -> bool:
    """Whether a RUNNING row that started at `started_at` has outlived the timeout."""
    return started_at is not None and now - started_at > timedelta(seconds=timeout_seconds)
