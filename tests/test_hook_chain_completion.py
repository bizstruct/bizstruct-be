"""POST /api/internal/hook — chain progression and completion.

Covers the bug an earlier e2e run reproduced live: a hook for a block whose
BLOCK_CHAIN position happened to be last, arriving while earlier blocks were
still empty, raised IndexError -> 500 instead of being treated as "nothing
left to enqueue yet". app.block_chain.next_block() replaces the raw index
arithmetic that caused it.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.block_chain import BLOCK_CHAIN
from app.models import Project
from tests.conftest import INTERNAL_HEADERS
from tests.test_hook_architecture import _valid_architecture
from tests.test_hook_empathy_map import _valid_empathy_map
from tests.test_hook_scenario import _valid_scenario
from tests.test_hook_pitch import _valid_pitch
from tests.test_hook_hypotheses import _valid_hypotheses
from tests.test_hook_models_options import _valid_models_options
from tests.test_hook_canvas import _valid_canvas

# Some BLOCK_CHAIN blocks are validated against a bizstruct_domain model on
# hook receipt (see app.routers.internal._DOMAIN_VALIDATED_BLOCKS); a bare
# {"stub": True} payload fails their validation, so those blocks need a
# real, valid stub instead. Everything else still accepts the bare stub.
_STUB_DATA = {
    "architecture": _valid_architecture,
    "empathy_map": _valid_empathy_map,
    "scenario": _valid_scenario,
    "pitch": _valid_pitch,
    "hypotheses": _valid_hypotheses,
    "models_options": _valid_models_options,
    "canvas": _valid_canvas,
}


def _stub_data_for(block: str) -> dict:
    factory = _STUB_DATA.get(block)
    return factory() if factory else {"stub": True}


def _hook_body(project_id, block: str, data) -> dict:
    return {
        "projectId": str(project_id),
        "block": block,
        "status": "success",
        "data": data,
    }


async def _make_project_missing(db_session, missing_block: str) -> Project:
    """A project with every BLOCK_CHAIN block filled except `missing_block`."""
    filled = {b: _stub_data_for(b) for b in BLOCK_CHAIN if b != missing_block}
    p = Project(
        id=uuid4(),
        title="Test Project",
        idea="A test idea",
        status="generating",
        **filled,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


async def test_last_block_in_chain_completes_without_enqueue(client, db_session):
    last_block = BLOCK_CHAIN[-1]
    p = await _make_project_missing(db_session, last_block)

    with patch("app.routers.internal.enqueue_block", MagicMock()) as enqueue_mock:
        resp = await client.post(
            "/api/internal/hook",
            json=_hook_body(p.id, last_block, _stub_data_for(last_block)),
            headers=INTERNAL_HEADERS,
        )

    assert resp.status_code == 200
    enqueue_mock.assert_not_called()

    await db_session.refresh(p)
    assert p.status == "completed"


async def test_intermediate_block_enqueues_the_next_one(client, db_session):
    first_block = BLOCK_CHAIN[0]
    second_block = BLOCK_CHAIN[1]
    p = Project(
        id=uuid4(),
        title="Test Project",
        idea="A test idea",
        status="generating",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    with patch("app.routers.internal.enqueue_block", MagicMock()) as enqueue_mock:
        resp = await client.post(
            "/api/internal/hook",
            json=_hook_body(p.id, first_block, _stub_data_for(first_block)),
            headers=INTERNAL_HEADERS,
        )

    assert resp.status_code == 200
    enqueue_mock.assert_called_once_with(str(p.id), second_block, False, "en")

    await db_session.refresh(p)
    assert p.status != "completed"


async def test_out_of_order_last_block_hook_does_not_crash(client, db_session):
    """The exact scenario the e2e run hit: a hook for a chain block arrives
    while earlier blocks are still empty. Must not 500, regardless of where
    in BLOCK_CHAIN that block sits."""
    p = Project(
        id=uuid4(),
        title="Test Project",
        idea="A test idea",
        status="generating",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    architecture_block = "architecture"
    resp = await client.post(
        "/api/internal/hook",
        json=_hook_body(
            p.id,
            architecture_block,
            {
                "epicenter": "customer_driven",
                "epicenter_rationale": "A rationale long enough in English to satisfy the field's validation here.",
                "pattern": "free",
                "pattern_subtype": "freemium",
                "pattern_rationale": "A pattern rationale long enough in English to satisfy validation for this test.",
            },
        ),
        headers=INTERNAL_HEADERS,
    )

    assert resp.status_code == 200
    await db_session.refresh(p)
    assert p.architecture is not None
    assert p.status == "generating"  # not all blocks filled yet
