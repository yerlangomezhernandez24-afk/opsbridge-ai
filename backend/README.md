# Backend de OpsBridge AI

This directory contains the FastAPI application, ticket domain and persistence, local authentication, role-scoped FTS5 knowledge retrieval, governed action proposals, independent approval, and a strictly synthetic VPN simulator. The React frontend lives in `../frontend`. This release does not implement comments, a verified LLM, embeddings, autonomous agents, or real infrastructure automation.

## Prerequisite

Install 64-bit Python 3.12 from a trusted source and ensure the Windows Python launcher (`py`) is available. The package metadata also permits Python 3.11, but the verified phases have executed only with Python 3.12.14.

## Setup on Windows

From the repository root:

```powershell
.\backend\scripts\setup.ps1
```

The script creates `backend\.venv`, installs the exact locked dependency set, installs the local package in editable mode, and runs `pip check`. It does not change execution policy or global Python packages.

If `py` is unavailable but Python is installed elsewhere:

```powershell
.\backend\scripts\setup.ps1 -PythonExecutable 'C:\Path\To\python.exe'
```

## Quality checks

```powershell
.\backend\scripts\test.ps1
```

This runs Ruff, mypy, pytest, and `pip check` with the virtual environment.

## Run locally

```powershell
.\backend\scripts\run.ps1
```

The server binds to `127.0.0.1:8000`. OpenAPI is available at <http://127.0.0.1:8000/docs> and the schema at <http://127.0.0.1:8000/openapi.json>.

If port 8000 is already occupied, choose another loopback port without stopping an unrelated process:

```powershell
.\backend\scripts\run.ps1 -Port 8765
```

Health checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Stop the foreground server with `Ctrl+C`. The script does not create a background process.

## Configuration

Defaults are safe for local development. Copy `.env.example` to `.env` only when overrides are necessary. `.env`, local databases, logs, and virtual environments are ignored by Git. The current backend accepts only loopback hosts and SQLite URLs.

## Persistence and migrations

- SQLAlchemy records are separate from domain objects.
- `SqlAlchemyUnitOfWork` owns explicit commit/rollback boundaries.
- SQLite enables foreign keys, WAL for file databases, and a bounded busy timeout.
- Revision `0001_ticket_persistence` creates `tickets`, `ticket_events`, and `ticket_key_sequences`.
- Revision `0002_local_auth` incrementally creates `users` and `auth_sessions`.
- Revision `0003_ticket_api_idempotency` adds persistent creation idempotency and ticket-list indexes.
- Revision `0004_knowledge_fts` adds synthetic knowledge documents, chunks and SQLite FTS5 retrieval.
- Revision `0005_governed_automation` adds proposals, decisions, executions, tool audit and the VPN simulator state.
- Application startup does not migrate or delete databases automatically.

From `backend`, inspect and apply reviewed migrations with:

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic history
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```

The database URL comes from `OPSBRIDGE_DATABASE_URL`; the default remains under `backend/var/` and is ignored by Git. Always back up meaningful local data before applying a future migration.

Downgrade was verified only on disposable pytest databases. Do not downgrade a user database without a reviewed recovery plan. For future schema changes, create a new revision and review it before applying:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe reviewed change"
```

Never edit or replace an already applied revision merely to make a changed model pass.

## Local authentication administration

Apply migrations before creating users. Passwords are read interactively and are never accepted as command-line arguments:

```powershell
Push-Location .\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
Pop-Location
.\backend\scripts\create-user.ps1 --login demo.requester --display-name "Demo Requester" --role requester
```

Approved roles are `requester`, `technician`, and `approver`. Passwords must contain 12–128 characters. The command stores only an Argon2id hash. Duplicate logins are rejected without printing database details.

The default browser origin is exactly `http://127.0.0.1:5173`. Session cookies are `HttpOnly` and `SameSite=Lax`; `Secure=false` is accepted only for this loopback HTTP development profile. Configure an HTTPS origin and `OPSBRIDGE_SESSION_COOKIE_SECURE=true` whenever TLS is used. Sessions expire after 8 hours absolutely or 30 minutes idle by default.

## Ticket API

Implemented routes include `POST/GET /api/v1/tickets`, aggregate summaries, `GET/PATCH /api/v1/tickets/{ticket_id}`, server-authorized transition options, transitions and paginated timeline; knowledge search and cited chunks; action proposals, approval decisions, exactly-once simulated executions, VPN simulator state and truthful AI capability status. Mutations require the configured `Origin`, session cookie and `X-CSRF-Token`. Creation additionally requires a canonical UUID v4 `Idempotency-Key`; versioned operations require `If-Match: "<version>"` where specified by OpenAPI.

Requesters see only their own tickets. Technicians and approvers may read the queue; approvers cannot mutate tickets. A technician cannot mutate a ticket assigned to another technician. `PATCH` is intentionally limited to category, impact and urgency because those are the editable operations currently supported by the domain.

Knowledge uses lexical SQLite FTS5 with role filters and citations. It is not semantic RAG or a generative model. Automation uses deterministic rules and accepts only `DEMO-VPN-NNN`; it revalidates ticket status, assignment, version, proposal hash, expiry and separation of duties before recording a simulated effect. `LOCAL_LLM_PENDING` is intentional.

