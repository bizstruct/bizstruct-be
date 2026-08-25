"""Startup validation: every BLOCK_CHAIN entry must map to a known STAGES id."""
from bizstruct_domain.chain import STAGES

from app.routers.internal import BLOCK_CHAIN, _STAGE_ID_OVERRIDES, _validate_block_chain_against_stages


def test_validation_ran_cleanly_at_import_and_is_idempotent():
    _validate_block_chain_against_stages()


def test_every_block_resolves_to_a_known_stage():
    known_stage_ids = {s.id for s in STAGES}
    for block_id in BLOCK_CHAIN:
        stage_id = _STAGE_ID_OVERRIDES.get(block_id, block_id)
        assert stage_id in known_stage_ids, (
            f"block '{block_id}' resolves to stage '{stage_id}', "
            "which does not exist in bizstruct_domain.chain.STAGES"
        )


def test_validation_raises_on_unknown_block(monkeypatch):
    monkeypatch.setattr(
        "app.routers.internal.BLOCK_CHAIN",
        [*BLOCK_CHAIN, "not_a_real_stage"],
    )
    try:
        _validate_block_chain_against_stages()
        assert False, "expected RuntimeError for an unregistered stage id"
    except RuntimeError as e:
        assert "not_a_real_stage" in str(e)
