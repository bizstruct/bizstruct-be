"""Domain-built StageResults for tests: what ml would answer for each row.

Builds persisted artifacts with the domain's own models (`*Generated` contracts
converted with `from_generated`) and the ids ml derives (`derive_artifact_id`),
so a simulated worker can walk a whole project against be's real endpoints.
The recipes mirror the builders of the bizstruct-domain tests, which are not
shipped with the package.
"""

from collections.abc import Callable, Sequence
from itertools import count
from typing import Any

from bizstruct_domain import (
    ArtifactRecord,
    ArtifactType,
    Brief,
    BusinessCase,
    BusinessCaseGenerated,
    Canvas,
    CanvasGenerated,
    CanvasSection,
    ConsistencyReport,
    ConsistencyViolation,
    CustomerScenario,
    CustomerScenarioGenerated,
    EmpathyMap,
    EmpathyMapGenerated,
    Epicenter,
    EpicenterClassification,
    EnvironmentScan,
    EnvironmentScanGenerated,
    Errc,
    ErrcGenerated,
    ERRCActionType,
    FutureScenario,
    FutureScenarioGenerated,
    Ideation,
    IdeationGenerated,
    PairwiseSegmentScoreGenerated,
    PatternsGenerated,
    Pitch,
    PitchGenerated,
    SegmentRelationType,
    SegmentPairGenerated,
    Stage,
    StageErrorCode,
    StageFailure,
    StageResult,
    Storytelling,
    StorytellingGenerated,
    Swot,
    SwotCluster,
    SwotGenerated,
    derive_artifact_id,
    patterns_from_generated,
)
from bizstruct_domain import StageRow as WireRow
from bizstruct_domain.schemas.canvas import CanvasSectionsGenerated, CanvasCardDraft
from bizstruct_domain.schemas.enums import (
    THREAT_QUESTIONS_BY_CLUSTER,
    StorytellingFormat,
    StorytellingGoal,
    StorytellingPerspective,
)
from bizstruct_domain.schemas.future_scenario import AdaptationQuestion, FutureScenarioVariant
from bizstruct_domain.schemas.optional_inputs import SalesScenario, Source
from bizstruct_domain.schemas.pattern import CanvasGroupGenerated
from bizstruct_domain.schemas.storytelling import CanvasReference
from bizstruct_domain.schemas.swot import SwotAxisStatement, SwotClusterResult, SwotOpportunity, SwotThreat

A = ArtifactType


def candidates(n: int) -> list[str]:
    return [f"Segment {k + 1}" for k in range(n)]


def error_report() -> ConsistencyReport:
    """A report with an error-level violation: the row ends up awaiting a decision."""
    return ConsistencyReport(
        score=2,
        violations=[
            ConsistencyViolation(rule_id="test_rule", severity="error", message="The artifacts contradict each other.", artifact_ids=["x"]),
        ],
    )


def warning_report() -> ConsistencyReport:
    return ConsistencyReport(
        score=4,
        violations=[
            ConsistencyViolation(rule_id="test_rule", severity="warning", message="Worth a second look.", artifact_ids=["x"]),
        ],
    )


def _record(artifact_id: str, artifact_type: ArtifactType, model: Any) -> ArtifactRecord:
    return ArtifactRecord(id=artifact_id, type=artifact_type, data=model.model_dump(mode="json"))


def _cluster(kind: SwotCluster) -> SwotClusterResult:
    axis = lambda score: SwotAxisStatement(positive_statement="pos", negative_statement="neg", score=score, importance=5, certainty=5)
    return SwotClusterResult(
        cluster=kind,
        axis_statements=[axis(1), axis(2)],
        opportunities=[SwotOpportunity(text="opportunity", score=3)],
        threats=[SwotThreat(question=q, text="threat", score=1) for q in THREAT_QUESTIONS_BY_CLUSTER[kind]],
    )


def _canvas_generated(tag: str = "") -> CanvasGenerated:
    cards = lambda name: [CanvasCardDraft(text=f"{name} card {n}{tag}") for n in (1, 2)]
    return CanvasGenerated(sections=CanvasSectionsGenerated(**{name: cards(name) for name in CanvasSectionsGenerated.model_fields}))


def _artifact_id(row: WireRow, artifact_type: ArtifactType) -> str:
    """The id of the single artifact of `artifact_type` that `row` holds."""
    return next(a.id for a in row.artifacts if a.type == artifact_type)


def _rows_of(rows: Sequence[WireRow], stage: Stage, ids: Sequence[str]) -> list[WireRow]:
    by_id = {r.id: r for r in rows}
    found = [by_id[i] for i in ids]
    assert all(r.stage == stage for r in found), (stage, ids)
    return found


def build_artifacts(
    row: WireRow,
    rows: Sequence[WireRow],
    *,
    project_id: str,
    segments: int = 1,
    groups: Sequence[Sequence[int]] = ((1,),),
) -> list[ArtifactRecord]:
    """The artifacts a worker would return for `row`, given the closure `rows` of its refs.

    `segments` is the number of segment candidates the brief proposes; `groups`
    gives the 1-based segment numbers of each Patterns group.
    """
    new_card = count(1)
    new_card_id: Callable[[], str] = lambda: f"card_{next(new_card)}"
    aid = lambda artifact_type, index=0: derive_artifact_id(row.id, artifact_type, index)

    match row.stage:
        case Stage.BRIEF:
            brief = Brief(
                idea_summary="A summary.", industry="Industry", customer_segment_candidates=candidates(segments),
                existing_resources=["resource"], gaps=["gap"],
            )
            return [_record(aid(A.BRIEF), A.BRIEF, brief)]

        case Stage.EMPATHY_MAP:
            generated = EmpathyMapGenerated(
                persona_name=f"Persona {row.instance_index + 1}", persona_demographics="D", sees=["s"], hears=["h"],
                thinks_and_feels=["t"], says_and_does=["d"], pains=["p"], gains=["g"],
            )
            return [_record(aid(A.EMPATHY_MAP), A.EMPATHY_MAP, EmpathyMap.from_generated(generated, id=aid(A.EMPATHY_MAP), project_id=project_id))]

        case Stage.CUSTOMER_SCENARIO:
            (empathy,) = _rows_of(rows, Stage.EMPATHY_MAP, row.refs[Stage.EMPATHY_MAP])
            generated = CustomerScenarioGenerated(situation_narrative="A narrative.", open_questions=["Which channel?"])
            model = CustomerScenario.from_generated(generated, id=aid(A.CUSTOMER_SCENARIO), empathy_map_id=_artifact_id(empathy, A.EMPATHY_MAP))
            return [_record(model.id, A.CUSTOMER_SCENARIO, model)]

        case Stage.IDEATION:
            (empathy,) = _rows_of(rows, Stage.EMPATHY_MAP, row.refs[Stage.EMPATHY_MAP])
            generated = IdeationGenerated(
                epicenter=EpicenterClassification(tags=[Epicenter.CUSTOMER_DRIVEN], rationale="Signals."),
                what_if_questions=["What if it were free?"],
            )
            model = Ideation.from_generated(generated, id=aid(A.IDEATION), empathy_map_id=_artifact_id(empathy, A.EMPATHY_MAP))
            return [_record(model.id, A.IDEATION, model)]

        case Stage.PATTERNS:
            maps = sorted((r for r in rows if r.stage == Stage.EMPATHY_MAP), key=lambda r: r.instance_index)
            segment_ids = {f"S{k + 1}": _artifact_id(m, A.EMPATHY_MAP) for k, m in enumerate(maps)}
            pairs = [
                PairwiseSegmentScoreGenerated(
                    segment_pair=SegmentPairGenerated(segment_alias_a=f"S{a}", segment_alias_b=f"S{b}"), synergy=3, conflict=0
                )
                for a in range(1, len(maps) + 1)
                for b in range(a + 1, len(maps) + 1)
            ]
            generated = PatternsGenerated(
                pairwise_scores=pairs,
                groups=[
                    CanvasGroupGenerated(segment_aliases=[f"S{n}" for n in g], relation_type=SegmentRelationType.SEGMENTED)
                    for g in groups
                ],
                pattern_tags=[],
            )
            model = patterns_from_generated(
                generated, id=aid(A.PATTERNS), project_id=project_id, segment_ids=segment_ids,
                group_ids=[f"group_{k + 1}" for k in range(len(groups))],
            )
            return [_record(model.id, A.PATTERNS, model)]

        case Stage.CANVAS:
            (patterns_row,) = _rows_of(rows, Stage.PATTERNS, row.refs[Stage.PATTERNS])
            patterns = next(a for a in patterns_row.artifacts if a.type == A.PATTERNS).data
            group = patterns["groups"][row.instance_index]
            model = Canvas.from_generated(
                _canvas_generated(), id=aid(A.CANVAS, 1), group_id=group["id"],
                empathy_map_ids=group["empathy_map_ids"], version=1, new_card_id=new_card_id,
            )
            return [_record(model.id, A.CANVAS, model)]

        case Stage.SWOT_ERRC_CYCLE:
            (canvas_row,) = _rows_of(rows, Stage.CANVAS, row.refs[Stage.CANVAS])
            canvas_v1 = next(a for a in canvas_row.artifacts if a.type == A.CANVAS)
            swot_1, swot_2 = aid(A.SWOT, 1), aid(A.SWOT, 2)
            canvas_v2 = Canvas.from_generated(
                _canvas_generated(" (level 1)"), id=aid(A.CANVAS, 2), group_id=canvas_v1.data["group_id"],
                empathy_map_ids=canvas_v1.data["empathy_map_ids"], version=2, previous_version_id=canvas_v1.id,
                new_card_id=new_card_id,
            )
            swots = [
                Swot.from_generated(
                    SwotGenerated(clusters=[_cluster(k) for k in SwotCluster]),
                    id=sid, canvas_id=cid, canvas_version=version, environment_scan_id=None,
                )
                for sid, cid, version in ((swot_1, canvas_v1.id, 1), (swot_2, canvas_v2.id, 2))
            ]
            errc = Errc.from_generated(
                ErrcGenerated(moves=[{
                    "action": ERRCActionType.CREATE, "target_section": CanvasSection.CHANNELS, "new_text": "new card",
                    "opposite_side_impact": "impact", "rationale": "why",
                }]),
                id=aid(A.ERRC, 1), canvas_id=canvas_v1.id, swot_id=swot_1, from_version=1, to_version=2,
                result_canvas_id=canvas_v2.id,
            )
            return [
                _record(swots[0].id, A.SWOT, swots[0]),
                _record(errc.id, A.ERRC, errc),
                _record(canvas_v2.id, A.CANVAS, canvas_v2),
                _record(swots[1].id, A.SWOT, swots[1]),
            ]

        case Stage.STORYTELLING:
            canvas_id, _ = _canvas_and_swot(rows, row)
            generated = StorytellingGenerated(
                perspective=StorytellingPerspective.COMPANY, goal=StorytellingGoal.PITCHING_INVESTORS,
                format=StorytellingFormat.VIDEO_CLIP, narrative_text="A story.",
                canvas_references=[CanvasReference(section=CanvasSection.CHANNELS, note="n")],
            )
            model = Storytelling.from_generated(generated, id=aid(A.STORYTELLING), canvas_id=canvas_id)
            return [_record(model.id, A.STORYTELLING, model)]

        case Stage.FUTURE_SCENARIO:
            canvas_id, _ = _canvas_and_swot(rows, row)
            generated = FutureScenarioGenerated(
                uncertainty_drivers=["a", "b"],
                variants=[
                    FutureScenarioVariant(
                        name=f"v{i}", narrative="n",
                        adaptation_questions=[AdaptationQuestion(section=CanvasSection.CHANNELS, question="q")],
                    )
                    for i in range(2)
                ],
            )
            model = FutureScenario.from_generated(generated, id=aid(A.FUTURE_SCENARIO), canvas_id=canvas_id)
            return [_record(model.id, A.FUTURE_SCENARIO, model)]

        case Stage.PITCH:
            canvas_id, swot_id = _canvas_and_swot(rows, row)
            (storytelling,) = _rows_of(rows, Stage.STORYTELLING, row.refs[Stage.STORYTELLING])
            business_case = [r for r in rows if r.stage == Stage.BUSINESS_CASE and r.id in row.refs.get(Stage.BUSINESS_CASE, [])]
            # A section and the id of the optional input it summarises come together or not at all.
            generated = PitchGenerated(
                hook="h", business_model_summary="s", competitive_advantages=["a"], risk_analysis=["r"],
                team_section=None, financial_analysis_section="fin" if business_case else None,
            )
            model = Pitch.from_generated(
                generated, id=aid(A.PITCH), project_id=project_id, storytelling_id=_artifact_id(storytelling, A.STORYTELLING),
                canvas_id=canvas_id, swot_id=swot_id, team_info_id=None,
                business_case_id=_artifact_id(business_case[0], A.BUSINESS_CASE) if business_case else None,
            )
            return [_record(model.id, A.PITCH, model)]

        case Stage.BUSINESS_CASE:
            generated = BusinessCaseGenerated(
                market_benchmarks="m", breakeven_formula="f", sales_scenarios=[SalesScenario(name="n", description="d")],
                capital_and_operating_costs="c", funding_requirements="f", profit_potential_notes="p",
            )
            model = BusinessCase.from_generated(generated, id=aid(A.BUSINESS_CASE), project_id=project_id, sources=[_source()])
            return [_record(model.id, A.BUSINESS_CASE, model)]

        case Stage.ENVIRONMENT_SCAN:
            generated = EnvironmentScanGenerated(
                market_forces=["m"], industry_forces=["i"], key_trends=["t"], macroeconomic_forces=["e"],
            )
            model = EnvironmentScan.from_generated(generated, id=aid(A.ENVIRONMENT_SCAN), project_id=project_id, sources=[_source()])
            return [_record(model.id, A.ENVIRONMENT_SCAN, model)]

    raise AssertionError(f"no recipe for {row.stage}")


def _source() -> Source:
    return Source(title="Report", retrieved_at="2026-09-30", note="supports figure")


def _canvas_and_swot(rows: Sequence[WireRow], row: WireRow) -> tuple[str, str]:
    """The id of the cycle's final canvas (v2) and its Swot, found through the row's cycle ref."""
    (cycle,) = _rows_of(rows, Stage.SWOT_ERRC_CYCLE, row.refs[Stage.SWOT_ERRC_CYCLE])
    canvases = [a for a in cycle.artifacts if a.type == A.CANVAS]
    final = max(canvases, key=lambda a: a.data["version"])
    swot = next(a for a in cycle.artifacts if a.type == A.SWOT and a.data["canvas_version"] == final.data["version"])
    return final.id, swot.id


def success(
    row: WireRow,
    rows: Sequence[WireRow],
    *,
    project_id: str,
    segments: int = 1,
    groups: Sequence[Sequence[int]] = ((1,),),
    consistency: ConsistencyReport | None = None,
) -> StageResult:
    return StageResult(
        project_id=project_id,
        stage_row_id=row.id,
        attempt_id=row.attempt_id or "",
        status="success",
        artifacts=build_artifacts(row, rows, project_id=project_id, segments=segments, groups=groups),
        consistency=consistency,
    )


def failure(row: WireRow, *, project_id: str, code: StageErrorCode = StageErrorCode.GENERATION_FAILED) -> StageResult:
    return StageResult(
        project_id=project_id,
        stage_row_id=row.id,
        attempt_id=row.attempt_id or "",
        status="failed",
        error=StageFailure(code=code, message="The model failed."),
    )
