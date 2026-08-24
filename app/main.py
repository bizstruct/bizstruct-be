import uuid

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.pubsub import get_negotiate_url
from app.routers import blocks, generation, internal, models, projects

app = FastAPI(
    title="BizStruct API",
    description="AI-driven business modeling SaaS backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(blocks.router)
app.include_router(generation.router)
app.include_router(internal.router)
app.include_router(models.router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/negotiate", tags=["pubsub"])
async def negotiate(project_id: uuid.UUID = Query(...)) -> dict[str, str]:
    if not settings.azure_web_pubsub_connection_string:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="PubSub not configured")
    return {"url": get_negotiate_url(str(project_id))}
