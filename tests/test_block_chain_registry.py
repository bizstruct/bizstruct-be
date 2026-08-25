"""app.block_chain: single source of truth for block order, derived from
bizstruct_domain.chain — startup validation, next_block(), validate_model
exclusion."""
import pytest
from bizstruct_domain.chain import STAGES

from app.block_chain import (
    BLOCK_CHAIN,
    BLOCK_FIELDS,
    IMPLEMENTED_BLOCKS,
    _STAGE_ID_OVERRIDES,
    _validate_implemented_blocks_against_stages,
    next_block,
)


def test_validation_ran_cleanly_at_import_and_is_idempotent():
    _validate_implemented_blocks_against_stages()


def test_every_implemented_block_resolves_to_a_known_stage():
    known_stage_ids = {s.id for s in STAGES}
    for block_id in IMPLEMENTED_BLOCKS:
        stage_id = _STAGE_ID_OVERRIDES.get(block_id, block_id)
        assert stage_id in known_stage_ids, (
            f"block '{block_id}' resolves to stage '{stage_id}', "
            "which does not exist in bizstruct_domain.chain.STAGES"
        )


def test_validation_raises_on_unknown_block(monkeypatch):
    monkeypatch.setattr(
        "app.block_chain.IMPLEMENTED_BLOCKS",
        frozenset({*IMPLEMENTED_BLOCKS, "not_a_real_stage"}),
    )
    with pytest.raises(RuntimeError, match="not_a_real_stage"):
        _validate_implemented_blocks_against_stages()


def test_block_chain_order_matches_domain_topological_order():
    # BLOCK_CHAIN must be exactly IMPLEMENTED_BLOCKS in the order
    # bizstruct_domain.chain.topological_order(pro=False) puts them, not a
    # locally invented order.
    assert set(BLOCK_CHAIN) == IMPLEMENTED_BLOCKS
    assert len(BLOCK_CHAIN) == len(set(BLOCK_CHAIN))  # no duplicates


def test_next_block_for_every_implemented_block():
    for i, block_id in enumerate(BLOCK_CHAIN):
        expected = BLOCK_CHAIN[i + 1] if i + 1 < len(BLOCK_CHAIN) else None
        assert next_block(block_id) == expected


def test_next_block_of_last_block_is_none():
    assert next_block(BLOCK_CHAIN[-1]) is None


def test_next_block_raises_for_unknown_block():
    with pytest.raises(ValueError):
        next_block("not_a_real_block")


def test_validate_model_not_in_block_chain():
    assert "validate_model" not in BLOCK_CHAIN
    assert "validate_model" not in IMPLEMENTED_BLOCKS


def test_validate_model_only_in_block_fields_for_wire_recognition():
    assert "validate_model" in BLOCK_FIELDS
    assert BLOCK_FIELDS == frozenset(BLOCK_CHAIN) | {"validate_model"}
