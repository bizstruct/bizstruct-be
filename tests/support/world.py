"""An in-memory project for the pure orchestration tests: wire rows only, no database.

Plays both sides of the contract with the real functions of the app and the
domain: the planner creates rows, the domain says which are ready, a worker
double answers with domain-built artifacts, and the planner expands again.
"""

from collections.abc import Sequence
from itertools import count

from bizstruct_domain import (
    ConsistencyReport,
    Stage,
    StageResult,
    StageStatus,
    project_status,
    ready_rows,
)
from bizstruct_domain import StageRow as WireRow

from app.services.orchestration import NewRow, expand_rows, initial_rows, result_problems, success_path
from tests.support import artifacts

PROJECT_ID = "project_001"


class World:
    def __init__(
        self,
        segments: int = 1,
        groups: Sequence[Sequence[int]] = ((1,),),
        enabled: Sequence[Stage] = (),
    ) -> None:
        self.segments = segments
        self.groups = groups
        self.enabled = list(enabled)
        self.rows: list[WireRow] = []
        self._ids = count(1)
        self._attempts = count(1)
        self.add(initial_rows(self.enabled, self.new_id))

    def new_id(self) -> str:
        return f"r{next(self._ids)}"

    def add(self, specs: Sequence[NewRow]) -> None:
        for spec in specs:
            self.rows.append(
                WireRow(id=spec.id, stage=spec.stage, instance_index=spec.instance_index, status=StageStatus.PENDING, refs=spec.refs)
            )

    def row(self, row_id: str) -> WireRow:
        return next(r for r in self.rows if r.id == row_id)

    def of(self, stage: Stage) -> list[WireRow]:
        return sorted((r for r in self.rows if r.stage == stage), key=lambda r: r.instance_index)

    def ready(self) -> tuple[str, ...]:
        return ready_rows(self.rows, self.enabled)

    def expand(self) -> list[NewRow]:
        specs = expand_rows(self.rows, self.enabled, self.new_id)
        self.add(specs)
        return specs

    @property
    def status(self) -> str:
        return project_status(self.rows, self.enabled)

    def start(self, row_id: str) -> WireRow:
        row = self.row(row_id)
        row.status = StageStatus.RUNNING
        row.attempt_id = f"attempt_{next(self._attempts)}"
        return row

    def result_for(self, row_id: str, consistency: ConsistencyReport | None = None) -> StageResult:
        return artifacts.success(
            self.row(row_id), self.rows, project_id=PROJECT_ID, segments=self.segments, groups=self.groups, consistency=consistency
        )

    def finish(self, row_id: str, consistency: ConsistencyReport | None = None) -> None:
        """What be does for a successful result: validate, store, walk the statuses."""
        result = self.result_for(row_id, consistency)
        row = self.row(row_id)
        assert result_problems(row, result, self.rows) == []
        row.artifacts = result.artifacts
        row.consistency = result.consistency
        row.status = success_path(consistency, auto_approve=False)[-1]

    def run_to_completion(self, limit: int = 200) -> int:
        """Starts and finishes ready rows, expanding after each, until nothing is ready. Returns the rows run."""
        ran = 0
        for _ in range(limit):
            ready = self.ready()
            if not ready:
                return ran
            for row_id in ready:
                self.start(row_id)
                self.finish(row_id)
                self.expand()
                ran += 1
        raise AssertionError("did not settle")
