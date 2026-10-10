"""Pure orchestration rules (app.services.orchestration): no database, no FastAPI."""

from datetime import datetime, timedelta, timezone

import pytest

import app.services.orchestration as orchestration
from bizstruct_domain import (
    ArtifactRecord,
    ArtifactType,
    Brief,
    ConsistencyReport,
    Stage,
    StageResult,
    StageStatus,
    validate_row_refs,
)
from bizstruct_domain import StageRow as WireRow

from app.services.orchestration import (
    expand_rows,
    initial_rows,
    is_stuck,
    result_problems,
    success_path,
)
from tests.support import artifacts
from tests.support.world import PROJECT_ID, World

S = Stage
D, P = StageStatus.DONE, StageStatus.PENDING


def sequence_ids():
    counter = iter(range(1, 1000))
    return lambda: f"n{next(counter)}"


def run_until(world: World, stage: Stage) -> None:
    """Runs ready rows until every row of `stage` that exists is done (and at least one exists)."""
    for _ in range(100):
        rows = world.of(stage)
        if rows and all(r.status == D for r in rows):
            return
        for row_id in world.ready():
            world.start(row_id)
            world.finish(row_id)
            world.expand()
    raise AssertionError(f"{stage} never finished")


def refs_of(rows: list[WireRow]) -> list[dict[Stage, list[str]]]:
    return [r.refs for r in rows]


# --- initial_rows ---------------------------------------------------------


def test_a_new_project_starts_with_just_the_brief():
    (brief,) = initial_rows([], sequence_ids())

    assert (brief.stage, brief.instance_index, brief.refs) == (S.BRIEF, 0, {})


def test_enabled_optional_stages_get_rows_that_take_the_brief():
    rows = initial_rows([S.BUSINESS_CASE, S.ENVIRONMENT_SCAN], sequence_ids())

    by_stage = {r.stage: r for r in rows}
    brief = by_stage[S.BRIEF]
    assert set(by_stage) == {S.BRIEF, S.BUSINESS_CASE, S.ENVIRONMENT_SCAN}
    assert by_stage[S.BUSINESS_CASE].refs == {S.BRIEF: [brief.id]}
    assert by_stage[S.ENVIRONMENT_SCAN].refs == {S.BRIEF: [brief.id]}


def test_a_disabled_optional_stage_gets_no_row():
    stages = {r.stage for r in initial_rows([S.ENVIRONMENT_SCAN], sequence_ids())}
    assert S.BUSINESS_CASE not in stages


def test_team_info_is_never_created_at_project_creation():
    stages = {r.stage for r in initial_rows([S.TEAM_INFO, S.BUSINESS_CASE], sequence_ids())}
    assert S.TEAM_INFO not in stages


def test_only_the_brief_is_ready_at_first():
    world = World(enabled=[S.ENVIRONMENT_SCAN, S.BUSINESS_CASE])
    brief = world.of(S.BRIEF)[0]
    assert world.ready() == (brief.id,)


# --- expand_rows: nothing happens before a row is DONE ---------------------


def test_nothing_is_created_while_the_brief_is_not_done():
    world = World(segments=3)
    world.start(world.of(S.BRIEF)[0].id)
    assert world.expand() == []


# --- expand_rows: brief DONE -------------------------------------------


def test_a_done_brief_with_one_candidate_creates_one_map_scenario_ideation_and_patterns():
    world = World(segments=1)
    run_until(world, S.BRIEF)

    assert [r.stage for r in world.rows if r.stage != S.BRIEF] == [S.EMPATHY_MAP, S.CUSTOMER_SCENARIO, S.IDEATION, S.PATTERNS]


def test_a_done_brief_with_three_candidates_creates_three_maps_each_with_scenario_and_ideation():
    world = World(segments=3, groups=((1, 2, 3),))
    run_until(world, S.BRIEF)
    brief = world.of(S.BRIEF)[0]

    maps = world.of(S.EMPATHY_MAP)
    assert [m.instance_index for m in maps] == [0, 1, 2]
    assert all(m.refs == {S.BRIEF: [brief.id]} for m in maps)
    assert len(world.of(S.CUSTOMER_SCENARIO)) == len(world.of(S.IDEATION)) == 3
    for m in maps:
        for stage in (S.CUSTOMER_SCENARIO, S.IDEATION):
            (row,) = [r for r in world.of(stage) if r.refs == {S.EMPATHY_MAP: [m.id]}]
            assert row.instance_index == 0  # the segment is found through refs, not through the index


def test_the_patterns_row_refs_every_scenario_and_ideation_row():
    world = World(segments=3, groups=((1, 2, 3),))
    run_until(world, S.BRIEF)

    (patterns,) = world.of(S.PATTERNS)
    assert patterns.refs == {
        S.CUSTOMER_SCENARIO: [r.id for r in world.of(S.CUSTOMER_SCENARIO)],
        S.IDEATION: [r.id for r in world.of(S.IDEATION)],
    }


def test_candidates_beyond_max_segments_are_not_given_maps(monkeypatch):
    # A Brief cannot hold more than MAX_SEGMENTS candidates, so hand the planner one that does.
    four = Brief.model_construct(
        idea_summary="s", industry="i", customer_segment_candidates=[f"c{k}" for k in range(4)],
        existing_resources=[], gaps=[],
    )
    monkeypatch.setattr(orchestration, "parse_artifact", lambda record: four)
    fresh = World(segments=3)
    fresh.start(fresh.of(S.BRIEF)[0].id)
    fresh.of(S.BRIEF)[0].status = D
    fresh.of(S.BRIEF)[0].artifacts = [ArtifactRecord(id="b", type=ArtifactType.BRIEF, data={})]

    created = fresh.expand()

    assert len([c for c in created if c.stage == S.EMPATHY_MAP]) == 3


def test_expanding_twice_never_creates_a_row_twice():
    world = World(segments=3, groups=((1, 2), (3,)))
    for _ in range(100):
        ready = world.ready()
        if not ready:
            break
        for row_id in ready:
            world.start(row_id)
            world.finish(row_id)
            world.expand()
            assert world.expand() == []  # a second pass finds nothing missing
    assert world.status == "completed"


def test_expansion_is_computed_from_what_exists_so_it_survives_a_retry_of_the_whole_step():
    world = World(segments=2, groups=((1, 2),))
    run_until(world, S.BRIEF)
    before = len(world.rows)
    # The same hook processed again (a redelivery that slipped through) adds nothing.
    assert expand_rows(world.rows, world.enabled, world.new_id) == []
    assert len(world.rows) == before


def test_every_created_row_has_valid_refs():
    world = World(segments=3, groups=((1,), (2, 3)), enabled=[S.ENVIRONMENT_SCAN, S.BUSINESS_CASE])
    world.run_to_completion()
    for row in world.rows:
        validate_row_refs(row.stage, row.refs)


# --- expand_rows: patterns DONE ---------------------------------------------


def maps_scenarios_ideations(world: World, numbers: tuple[int, ...]):
    maps = [world.of(S.EMPATHY_MAP)[n - 1] for n in numbers]
    by_map = lambda stage: [r for m in maps for r in world.of(stage) if r.refs == {S.EMPATHY_MAP: [m.id]}]
    return maps, by_map(S.CUSTOMER_SCENARIO), by_map(S.IDEATION)


def test_a_unified_patterns_creates_one_canvas_row_with_all_inputs():
    world = World(segments=3, groups=((1, 2, 3),))
    run_until(world, S.PATTERNS)

    (canvas,) = world.of(S.CANVAS)
    maps, scenarios, ideations = maps_scenarios_ideations(world, (1, 2, 3))
    assert canvas.instance_index == 0
    assert canvas.refs == {
        S.BRIEF: [world.of(S.BRIEF)[0].id],
        S.EMPATHY_MAP: [m.id for m in maps],
        S.CUSTOMER_SCENARIO: [r.id for r in scenarios],
        S.IDEATION: [r.id for r in ideations],
        S.PATTERNS: [world.of(S.PATTERNS)[0].id],
    }


def test_a_split_patterns_creates_one_canvas_row_per_group_in_group_order():
    world = World(segments=3, groups=((1, 2), (3,)))
    run_until(world, S.PATTERNS)

    canvases = world.of(S.CANVAS)
    assert [c.instance_index for c in canvases] == [0, 1]
    for canvas, numbers in zip(canvases, ((1, 2), (3,))):
        maps, scenarios, ideations = maps_scenarios_ideations(world, numbers)
        assert canvas.refs[S.EMPATHY_MAP] == [m.id for m in maps]
        assert canvas.refs[S.CUSTOMER_SCENARIO] == [r.id for r in scenarios]
        assert canvas.refs[S.IDEATION] == [r.id for r in ideations]


def test_canvas_rows_are_found_by_artifact_id_not_by_position():
    world = World(segments=3, groups=((3,), (1, 2)))  # the first group holds the LAST segment
    run_until(world, S.PATTERNS)

    first, second = world.of(S.CANVAS)
    assert first.refs[S.EMPATHY_MAP] == [world.of(S.EMPATHY_MAP)[2].id]
    assert second.refs[S.EMPATHY_MAP] == [world.of(S.EMPATHY_MAP)[0].id, world.of(S.EMPATHY_MAP)[1].id]


def test_no_canvas_row_exists_before_patterns_is_done():
    world = World(segments=2, groups=((1,), (2,)))
    run_until(world, S.IDEATION)
    assert world.of(S.CANVAS) == []


# --- expand_rows: canvas DONE -------------------------------------------


def test_a_done_canvas_creates_its_cycle_storytelling_future_scenario_and_pitch():
    world = World()
    run_until(world, S.CANVAS)

    canvas = world.of(S.CANVAS)[0]
    (cycle,) = world.of(S.SWOT_ERRC_CYCLE)
    (story,) = world.of(S.STORYTELLING)
    (future,) = world.of(S.FUTURE_SCENARIO)
    (pitch,) = world.of(S.PITCH)
    assert cycle.refs == {S.CANVAS: [canvas.id]}
    assert story.refs == {S.SWOT_ERRC_CYCLE: [cycle.id]}
    assert future.refs == {S.SWOT_ERRC_CYCLE: [cycle.id]}
    assert pitch.refs == {S.STORYTELLING: [story.id], S.SWOT_ERRC_CYCLE: [cycle.id]}
    assert all(r.instance_index == 0 for r in (cycle, story, future, pitch))


def test_the_cycle_refs_the_environment_scan_row_when_it_is_enabled():
    world = World(enabled=[S.ENVIRONMENT_SCAN])
    run_until(world, S.CANVAS)

    (cycle,) = world.of(S.SWOT_ERRC_CYCLE)
    assert cycle.refs == {S.CANVAS: [world.of(S.CANVAS)[0].id], S.ENVIRONMENT_SCAN: [world.of(S.ENVIRONMENT_SCAN)[0].id]}


def test_the_pitch_refs_the_business_case_row_when_it_is_enabled():
    world = World(enabled=[S.BUSINESS_CASE])
    run_until(world, S.CANVAS)

    (pitch,) = world.of(S.PITCH)
    assert pitch.refs[S.BUSINESS_CASE] == [world.of(S.BUSINESS_CASE)[0].id]


def test_the_pitch_refs_a_team_info_row_when_one_exists_and_the_stage_is_enabled():
    world = World(enabled=[S.TEAM_INFO])
    team = WireRow(id="team_row", stage=S.TEAM_INFO, status=D)
    world.rows.append(team)
    run_until(world, S.CANVAS)

    (pitch,) = world.of(S.PITCH)
    assert pitch.refs[S.TEAM_INFO] == ["team_row"]


def test_the_pitch_ignores_a_team_info_row_when_the_stage_is_not_enabled():
    world = World(enabled=[])
    world.rows.append(WireRow(id="team_row", stage=S.TEAM_INFO, status=D))
    run_until(world, S.CANVAS)

    (pitch,) = world.of(S.PITCH)
    assert S.TEAM_INFO not in pitch.refs


def test_each_canvas_gets_its_own_downstream_rows():
    world = World(segments=3, groups=((1, 2), (3,)))
    run_until(world, S.CANVAS)

    canvases = world.of(S.CANVAS)
    cycles = world.of(S.SWOT_ERRC_CYCLE)
    assert len(cycles) == len(canvases) == 2
    assert [c.refs[S.CANVAS] for c in cycles] == [[canvases[0].id], [canvases[1].id]]
    assert len(world.of(S.PITCH)) == len(world.of(S.STORYTELLING)) == len(world.of(S.FUTURE_SCENARIO)) == 2


def test_a_canvas_that_is_not_done_creates_nothing_downstream():
    world = World()
    run_until(world, S.PATTERNS)
    for row_id in world.ready():
        world.start(row_id)  # the canvas is running, not done
    assert world.expand() == []
    assert world.of(S.SWOT_ERRC_CYCLE) == []


# --- readiness through the planner's rows (domain functions) ----------------


def test_only_rows_whose_inputs_are_done_are_ready():
    world = World(segments=2, groups=((1, 2),))
    run_until(world, S.BRIEF)

    ready = world.ready()
    assert set(ready) == {r.id for r in world.of(S.EMPATHY_MAP)}  # scenario/ideation/patterns still wait


def test_an_enabled_optional_stage_blocks_its_consumer_until_it_is_done():
    world = World(enabled=[S.ENVIRONMENT_SCAN])
    for _ in range(100):
        ready = [r for r in world.ready() if world.row(r).stage != S.ENVIRONMENT_SCAN]
        if not ready:
            break
        for row_id in ready:
            world.start(row_id)
            world.finish(row_id)
            world.expand()

    (cycle,) = world.of(S.SWOT_ERRC_CYCLE)
    assert cycle.status == P
    assert cycle.id not in world.ready()  # the environment scan has not run

    scan = world.of(S.ENVIRONMENT_SCAN)[0]
    world.start(scan.id)
    world.finish(scan.id)
    assert cycle.id in world.ready()


def test_a_disabled_optional_stage_does_not_block_anything():
    world = World()
    world.run_to_completion()
    assert world.status == "completed"
    assert world.of(S.ENVIRONMENT_SCAN) == []


# --- whole-graph runs --------------------------------------------------------


@pytest.mark.parametrize(
    "segments,groups,expected_canvases",
    [(1, ((1,),), 1), (3, ((1, 2, 3),), 1), (3, ((1, 2), (3,)), 2)],
    ids=["one segment", "three in one group", "split in two"],
)
def test_a_whole_project_runs_to_completed(segments, groups, expected_canvases):
    world = World(segments=segments, groups=groups, enabled=[S.ENVIRONMENT_SCAN, S.BUSINESS_CASE])
    assert world.status == "running"

    world.run_to_completion()

    assert world.status == "completed"
    assert len(world.of(S.CANVAS)) == expected_canvases
    assert len(world.of(S.PITCH)) == expected_canvases
    assert all(r.status == D for r in world.rows)


def test_a_project_with_a_failed_row_is_failed():
    world = World()
    world.rows[0].status = StageStatus.ERROR
    assert world.status == "failed"


# --- result_problems -------------------------------------------------------


def running_brief(world: World) -> WireRow:
    return world.start(world.of(S.BRIEF)[0].id)


def test_a_valid_result_has_no_problems():
    world = World()
    row = running_brief(world)
    assert result_problems(row, world.result_for(row.id), world.rows) == []


def test_artifact_data_that_fails_its_schema_is_a_problem():
    world = World()
    row = running_brief(world)
    result = world.result_for(row.id)
    result.artifacts[0] = ArtifactRecord(id="x", type=ArtifactType.BRIEF, data={"industry": "only this"})

    problems = result_problems(row, result, world.rows)

    assert len(problems) == 1 and "brief" in problems[0]


def test_a_record_id_that_differs_from_the_artifacts_own_id_is_a_problem():
    world = World(segments=1)
    run_until(world, S.BRIEF)
    empathy = world.start(world.of(S.EMPATHY_MAP)[0].id)
    result = world.result_for(empathy.id)
    result.artifacts[0] = result.artifacts[0].model_copy(update={"id": "someone-elses-id"})

    problems = result_problems(empathy, result, world.rows)

    assert len(problems) == 1 and "differs" in problems[0]


def test_an_artifact_type_the_stage_cannot_hold_is_a_problem():
    world = World()
    row = running_brief(world)
    wrong = artifacts.build_artifacts(row, world.rows, project_id=PROJECT_ID)[0].model_copy(update={"type": ArtifactType.PITCH})
    result = StageResult(project_id=PROJECT_ID, stage_row_id=row.id, attempt_id=row.attempt_id, status="success", artifacts=[wrong])

    problems = result_problems(row, result, world.rows)

    assert any("cannot hold" in p for p in problems)


def test_duplicate_artifact_ids_are_a_problem():
    world = World()
    row = running_brief(world)
    record = world.result_for(row.id).artifacts[0]
    result = StageResult(project_id=PROJECT_ID, stage_row_id=row.id, attempt_id=row.attempt_id, status="success", artifacts=[record, record])

    assert any("duplicate" in p for p in result_problems(row, result, world.rows))


def test_a_cycle_result_with_only_canvases_has_none_of_its_own_artifacts():
    world = World()
    run_until(world, S.CANVAS)
    cycle = world.start(world.of(S.SWOT_ERRC_CYCLE)[0].id)
    only_canvas = [a for a in world.result_for(cycle.id).artifacts if a.type == ArtifactType.CANVAS]
    result = StageResult(project_id=PROJECT_ID, stage_row_id=cycle.id, attempt_id=cycle.attempt_id, status="success", artifacts=only_canvas)

    assert any("none of its own" in p for p in result_problems(cycle, result, world.rows))


def test_a_cycle_result_may_carry_the_canvas_versions_it_produced():
    world = World()
    run_until(world, S.CANVAS)
    cycle = world.start(world.of(S.SWOT_ERRC_CYCLE)[0].id)
    result = world.result_for(cycle.id)

    assert {a.type for a in result.artifacts} == {ArtifactType.SWOT, ArtifactType.ERRC, ArtifactType.CANVAS}
    assert result_problems(cycle, result, world.rows) == []


def test_a_patterns_group_that_names_an_unknown_empathy_map_is_a_problem():
    world = World(segments=2, groups=((1, 2),))
    run_until(world, S.IDEATION)
    patterns = world.start(world.of(S.PATTERNS)[0].id)
    result = world.result_for(patterns.id)
    data = dict(result.artifacts[0].data)
    data["groups"] = [dict(data["groups"][0], empathy_map_ids=[data["groups"][0]["empathy_map_ids"][0], "ghost-map"])]
    broken = StageResult(
        project_id=PROJECT_ID, stage_row_id=patterns.id, attempt_id=patterns.attempt_id, status="success",
        artifacts=[result.artifacts[0].model_copy(update={"data": data})],
    )

    problems = result_problems(patterns, broken, world.rows)

    assert any("ghost-map" in p for p in problems)


def test_a_patterns_group_naming_a_row_of_another_stage_is_a_problem():
    world = World(segments=1, groups=((1,),))
    run_until(world, S.IDEATION)
    patterns = world.start(world.of(S.PATTERNS)[0].id)
    result = world.result_for(patterns.id)
    scenario_artifact = world.of(S.CUSTOMER_SCENARIO)[0].artifacts[0].id
    data = dict(result.artifacts[0].data)
    data["groups"] = [dict(data["groups"][0], empathy_map_ids=[scenario_artifact])]
    broken = StageResult(
        project_id=PROJECT_ID, stage_row_id=patterns.id, attempt_id=patterns.attempt_id, status="success",
        artifacts=[result.artifacts[0].model_copy(update={"data": data})],
    )

    assert any(scenario_artifact in p for p in result_problems(patterns, broken, world.rows))


# --- success_path --------------------------------------------------------------


def test_no_report_goes_through_consistency_check_to_done():
    assert success_path(None, auto_approve=False) == (StageStatus.CONSISTENCY_CHECK, StageStatus.DONE)


def test_warnings_do_not_block_done():
    assert success_path(artifacts.warning_report(), auto_approve=False) == (StageStatus.CONSISTENCY_CHECK, StageStatus.DONE)


def test_a_clean_report_goes_to_done():
    assert success_path(ConsistencyReport(score=5), auto_approve=False)[-1] == StageStatus.DONE


def test_an_error_level_violation_awaits_a_decision():
    assert success_path(artifacts.error_report(), auto_approve=False) == (
        StageStatus.CONSISTENCY_CHECK,
        StageStatus.AWAITING_DECISION,
    )


def test_auto_approve_follows_an_error_level_violation_with_done():
    assert success_path(artifacts.error_report(), auto_approve=True) == (
        StageStatus.CONSISTENCY_CHECK,
        StageStatus.AWAITING_DECISION,
        StageStatus.DONE,
    )


def test_auto_approve_changes_nothing_when_there_is_no_error():
    assert success_path(ConsistencyReport(score=5), auto_approve=True) == (StageStatus.CONSISTENCY_CHECK, StageStatus.DONE)


# --- is_stuck ----------------------------------------------------------------


NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def test_a_row_past_the_timeout_is_stuck():
    assert is_stuck(NOW - timedelta(seconds=1801), NOW, 1800)


def test_a_row_within_the_timeout_is_not_stuck():
    assert not is_stuck(NOW - timedelta(seconds=1800), NOW, 1800)
    assert not is_stuck(NOW - timedelta(seconds=10), NOW, 1800)


def test_a_row_that_never_started_is_not_stuck():
    assert not is_stuck(None, NOW, 1800)


# --- the ids it assigns -----------------------------------------------------------


def test_new_rows_get_distinct_ids():
    world = World(segments=3, groups=((1,), (2, 3)))
    world.run_to_completion()
    ids = [r.id for r in world.rows]
    assert len(ids) == len(set(ids))
