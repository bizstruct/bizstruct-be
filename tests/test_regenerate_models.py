"""POST /api/generation/{project_id}/regenerate — models_options regeneration.

Regeneration must bypass bizstruct-ml's idempotency check (already generated
-> return without regenerating): it enqueues with force=True, unlike normal
chain progression which always uses the force=False default. See
app.servicebus.enqueue_block.
"""
from unittest.mock import MagicMock, patch

from tests.test_hook_models_options import _valid_models_options


async def test_regenerate_models_nulls_data_and_enqueues_with_force(client, project, db_session):
    project.models_options = _valid_models_options(selected_id=None)
    await db_session.commit()

    with patch("app.routers.generation.enqueue_block", MagicMock()) as enqueue_mock:
        resp = await client.post(f"/api/generation/{project.id}/regenerate")

    assert resp.status_code == 202
    enqueue_mock.assert_called_once_with(str(project.id), "models_options", True, "en")

    await db_session.refresh(project)
    assert project.models_options is None
    assert project.status == "generating"
