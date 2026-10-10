# bizstruct-be

Backend of BizStruct: a thin store and orchestrator for the generation pipeline. It keeps projects and stage rows (refs, statuses, artifacts), sends one queue message per ready row to `bizstruct-ml`, and applies the results `ml` posts back. See [docs/adr/0001-be-rows-and-orchestration.md](docs/adr/0001-be-rows-and-orchestration.md) and bizstruct-domain ADR-0011.

## Run

```bash
cp .env.example .env
docker compose up --build   # api + postgres; the api runs `alembic upgrade head`
```

The database schema changed incompatibly (ADR-0001): **recreate the database volume** (`docker compose down -v`) when upgrading from an older version.

## Develop

Dependencies are managed with `uv`; `bizstruct-domain` is pinned to a release tag in `pyproject.toml`.

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Test

Tests need a Postgres on `localhost:55432` with a database `bizstruct_test` (user/password `postgres`); the schema is recreated on every run. Azure is never contacted: the queue and the event publisher are replaced with in-memory fakes.

```bash
docker run -d --name bizstruct-test-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=bizstruct_test -p 127.0.0.1:55432:5432 postgres:15-alpine
uv run pytest
```

## API

Public (JWT, see `/docs`):

- `POST /api/generation` — create a project and start generating: `{title?, idea, language, enabledOptional?, autoApprove?}`
- `GET /api/projects`, `GET /api/projects/{id}` (status derived from rows; reading runs the stuck-row watchdog), `PATCH`, `DELETE`
- `POST /api/projects/{id}/rows/{row_id}/regenerate`, `…/approve`

Internal (header `x-api-key`, used by `bizstruct-ml`):

- `GET /api/internal/projects/{id}?row=<row_id>` — `ProjectSnapshot` (that row and the closure of its refs)
- `POST /api/internal/hook` — a `StageResult`; answers 200, 404, 409 or 422
