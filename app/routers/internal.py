import json
import logging
import uuid
from typing import Annotated, Any, Literal

from bizstruct_domain.blocks.architecture import Architecture
from bizstruct_domain.chain import STAGES
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import ValidationError as DomainValidationError
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Project
from app.pubsub import send_block_ready, send_generation_complete, send_validate_result
from app.schemas import CamelModel, ProjectResponse
from app.servicebus import enqueue_block

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])

DbDep = Annotated[AsyncSession, Depends(get_db)]

BLOCK_CHAIN: list[str] = [
    "models_options",
    "canvas_data",
    "empathy_map",
    "hypotheses",
    "pitch",
    "scenario",
    "what_if",
    "architecture",
]

BLOCK_FIELDS: frozenset[str] = frozenset(BLOCK_CHAIN) | {"validate_model"}

# This repo's wire-level block ids (queue message `block`, hook payload,
# Project column names) predate bizstruct_domain and don't all match its
# stage ids one-for-one. `canvas_data` here is `canvas` in STAGES; everything
# else lines up. This map bridges that one naming drift for the startup
# check below — it does NOT rename the wire protocol (out of scope: shared
# with bizstruct-ml and the frontend). See bizstruct-ml/generators/registry.py
# for the identical pattern used there.
_STAGE_ID_OVERRIDES: dict[str, str] = {
    "canvas_data": "canvas",
}

# Blocks with dedicated bizstruct_domain models. Everything else in
# BLOCK_CHAIN is still a bare dict[str, Any] — pilot slice, more blocks land
# in follow-up PRs the same way.
_DOMAIN_VALIDATED_BLOCKS: dict[str, type] = {
    "architecture": Architecture,
}


def _validate_block_chain_against_stages() -> None:
    """Fail fast on startup if a block this service handles has no matching stage.

    Every BLOCK_CHAIN entry must resolve (directly, or via
    `_STAGE_ID_OVERRIDES`) to a stage id in `bizstruct_domain.chain.STAGES`.
    This deliberately does NOT go the other way — STAGES includes stages
    (`brief`, `value_map`, `environment_scan`, `assessment`, ...) that no
    generator/block handling exists for yet, and that's expected in this
    pilot slice.
    """
    known_stage_ids = {s.id for s in STAGES}
    for block_id in BLOCK_CHAIN:
        stage_id = _STAGE_ID_OVERRIDES.get(block_id, block_id)
        if stage_id not in known_stage_ids:
            raise RuntimeError(
                f"BLOCK_CHAIN configuration error: block '{block_id}' "
                f"(resolved stage id '{stage_id}') is not a known stage in "
                "bizstruct_domain.chain.STAGES"
            )


_validate_block_chain_against_stages()


async def verify_internal_key(x_api_key: Annotated[str, Header()]) -> None:
    if x_api_key != settings.internal_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


InternalAuth = Annotated[None, Depends(verify_internal_key)]


class HookRequest(CamelModel):
    project_id: uuid.UUID
    block: str
    status: Literal["success", "failed"]
    data: dict[str, Any] | list[Any] | None = None
    error: str | None = None



@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project_internal(
    project_id: uuid.UUID,
    _: InternalAuth,
    db: DbDep,
) -> ProjectResponse:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.post("/hook", status_code=status.HTTP_200_OK)
async def ml_hook(
    body: HookRequest,
    background_tasks: BackgroundTasks,
    _: InternalAuth,
    db: DbDep,
) -> dict[str, str]:
    if body.block not in BLOCK_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown block: {body.block}",
        )

    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    project_id_str = str(body.project_id)

    if body.block == "validate_model":
        if body.status == "success" and body.data:
            model_id = str(body.data.get("model_id", ""))
            send_validate_result(project_id_str, model_id, body.data)
        return {"ok": "1"}

    if body.status == "success":
        block_data: Any = body.data

        domain_model = _DOMAIN_VALIDATED_BLOCKS.get(body.block)
        if domain_model is not None:
            try:
                validated = domain_model.model_validate(body.data)
            except DomainValidationError as e:
                errors = e.errors()
                logger.error(
                    "hook_schema_validation_failed",
                    extra={"project_id": project_id_str, "block": body.block, "errors": errors},
                )
                # A schema violation is not a transient failure — retrying the
                # same generation would produce the same invalid shape. So
                # this must NOT come back as a 5xx: bizstruct-ml currently
                # treats hook failure as abandon-and-retry, which would burn
                # through its retry budget re-generating the same bad output.
                # 422 is the deliberate signal for "unrecoverable, dead-letter
                # it, don't retry" — bizstruct-ml needs a follow-up change to
                # actually branch on this status code (see task summary).
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=json.loads(e.json()),
                )
            block_data = validated.model_dump(mode="json")

        setattr(project, body.block, block_data)
        flag_modified(project, body.block)

        # BLOCK_CHAIN (not BLOCK_FIELDS): "validate_model" is a side-channel
        # message, not a generation block, and isn't a Project column at all
        # — iterating BLOCK_FIELDS here would getattr() a nonexistent
        # attribute on every successful hook. Pre-existing bug, fixed as part
        # of touching this line for architecture validation.
        all_filled = all(getattr(project, field) is not None for field in BLOCK_CHAIN)
        if all_filled:
            project.status = "completed"
            logger.info("Project %s completed", project.id)

        await db.commit()
        send_block_ready(project_id_str, body.block, "success")
        if all_filled:
            send_generation_complete(project_id_str, "completed")
        else:
            next_idx = BLOCK_CHAIN.index(body.block) + 1
            background_tasks.add_task(enqueue_block, project_id_str, BLOCK_CHAIN[next_idx])

    else:
        project.status = "failed"
        logger.warning("Block %s failed for project %s: %s", body.block, project.id, body.error)
        await db.commit()
        send_block_ready(project_id_str, body.block, "failed")
        send_generation_complete(project_id_str, "failed")

    return {"ok": "1"}
