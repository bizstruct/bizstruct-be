"""Single source of truth for which blocks this service generates and in
what order — derived from bizstruct_domain.chain, not hand-maintained.

Used by both app/routers/internal.py (the ML hook: what's the next block to
enqueue, has everything been generated) and app/routers/generation.py
(which block starts a new project's generation).
"""

from bizstruct_domain.chain import STAGES, topological_order

# Blocks this service can actually generate — i.e. bizstruct-ml has a
# matching generator for each. This is deliberately NOT "every id in
# STAGES": brief, value_map, environment_scan, and assessment don't have
# generators yet (pilot slice), and STAGES also carries Pro-only stages this
# pipeline doesn't run at all.
IMPLEMENTED_BLOCKS: frozenset[str] = frozenset({
    "models_options",
    "canvas",
    "empathy_map",
    "hypotheses",
    "pitch",
    "scenario",
    "what_if",
    "architecture",
})


def _validate_implemented_blocks_against_stages() -> None:
    """Fail fast on startup if an implemented block has no matching stage.

    Every IMPLEMENTED_BLOCKS entry must be a stage id in
    `bizstruct_domain.chain.STAGES` — no id-mapping layer. (There used to
    be a `canvas_data` -> `canvas` _STAGE_ID_OVERRIDES bridge here; the
    wire-level block id was renamed to `canvas` instead of growing that
    mapping further — see the canvas rename commit.)
    """
    known_stage_ids = {s.id for s in STAGES}
    for block_id in IMPLEMENTED_BLOCKS:
        if block_id not in known_stage_ids:
            raise RuntimeError(
                f"IMPLEMENTED_BLOCKS configuration error: block '{block_id}' "
                "is not a known stage in bizstruct_domain.chain.STAGES"
            )


_validate_implemented_blocks_against_stages()


def _implemented_block_order() -> tuple[str, ...]:
    """Generation order for IMPLEMENTED_BLOCKS.

    Derived from bizstruct_domain.chain.topological_order(pro=False),
    filtered down to only the blocks this service actually generates — the
    Basic-mode methodological order (see bizstruct-domain's ADR-0001), not a
    locally invented one.
    """
    return tuple(
        stage_id for stage_id in topological_order(pro=False) if stage_id in IMPLEMENTED_BLOCKS
    )


BLOCK_CHAIN: tuple[str, ...] = _implemented_block_order()

# validate_model is a side-channel message (idea validation), not a
# generation block — it has no stage in STAGES and never appears in
# BLOCK_CHAIN. It's included here only because the hook endpoint accepts it
# as a recognized wire block id; do not fold it into BLOCK_CHAIN or iterate
# it as if it were a Project column.
BLOCK_FIELDS: frozenset[str] = frozenset(BLOCK_CHAIN) | {"validate_model"}


def next_block(current: str) -> str | None:
    """The block after `current` in BLOCK_CHAIN.

    Returns None if `current` is the last block in the chain — a normal,
    successful end of generation, not an error condition. Raises ValueError
    if `current` isn't in BLOCK_CHAIN at all (a caller bug, not a runtime
    data problem).
    """
    try:
        idx = BLOCK_CHAIN.index(current)
    except ValueError:
        raise ValueError(f"'{current}' is not a block in BLOCK_CHAIN") from None
    if idx + 1 >= len(BLOCK_CHAIN):
        return None
    return BLOCK_CHAIN[idx + 1]
