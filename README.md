# Sprintern

Internship alert aggregator. The foundation uses Next.js for the web app, FastAPI for the API and background work, and PostgreSQL for application data. Docker PostgreSQL is used locally; Supabase PostgreSQL and Auth are intended for production.

## Problem and MVP

Internship listings can receive a large number of applications within hours. Sprintern polls structured job sources, normalizes and deduplicates listings, matches them to a student's saved preferences, and delivers Telegram or email alerts.

The MVP includes Greenhouse, Lever, RemoteOK, and one GitHub-hosted internship repository; deterministic keyword matching; Supabase authentication; filters; a matched-job feed; applied status; and instant or batched notifications. AI classification, embeddings, recommendations, Ashby, We Work Remotely, Workable, SMS, and auto-apply are deliberately deferred.

## Architecture

```text
Next.js ── bearer token ──> FastAPI ── SQLAlchemy ──> PostgreSQL
   │                            │                       local: Docker
   └── Supabase Auth            ├── ingestion          prod: Supabase
                                ├── matching
APScheduler ── workflows ───────└── notifications ──> Telegram / Resend
```

Backend responsibilities are intentionally separated:

- `routes` translates HTTP requests and responses; it does not contain business logic.
- `schemas` validates API and ingestion boundaries with Pydantic.
- `repositories` owns database queries and user-ownership filtering.
- `services` coordinates application workflows and transaction boundaries.
- `ingestion/adapters` only fetches and maps one external source.
- `ingestion/normalization` produces a shared source-neutral representation.
- `ingestion/deduplication` resolves source records to canonical jobs.
- `matching` explains why a job matches a filter.
- `notifications` creates and delivers idempotent channel-specific messages.
- `scheduler` triggers workflows without containing their implementation.

The ingestion path is `fetch → validate → normalize → deduplicate → persist → match → notify`. Adapters never write to the database or send notifications, which keeps source-specific changes isolated and independently testable.

### Architectural decisions and tradeoffs

- FastAPI and SQLAlchemy own application data. Using Prisma as a second database layer would create competing models and migrations.
- Supabase owns identity and sessions; the application owns a linked profile. FastAPI validates tokens and remains the authorization boundary.
- Canonical jobs and source occurrences are separate records. This preserves provenance while allowing cross-source deduplication.
- PostgreSQL arrays and JSONB keep MVP preference and source metadata modeling compact. More normalized child tables may be justified if analytics become complex.
- Notification deliveries are durable database records rather than a Boolean flag, enabling idempotency, retries, and provider diagnostics.
- APScheduler is sufficient for one small worker. It is not a distributed queue and would be replaced by Celery/Redis if horizontal worker scaling becomes necessary.
- Keyword matching ships before AI so the end-to-end system is measurable before adding cost and nondeterminism.
- pgvector will live in PostgreSQL rather than a separate vector database because expected data volume does not justify another service.

## Development workflow

Each major component starts with a short design explanation and tradeoff review, followed by implementation, edge-case tests, and a README update. MVP milestones are completed and reviewed before post-MVP AI work begins.

## Requirements

- Node.js 24+
- Python 3.12+
- Docker Desktop

## First-time setup (Windows PowerShell)

```powershell
Copy-Item .env.example .env
npm.cmd install
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
docker compose up -d
```

Keep the local `DATABASE_URL` from `.env.example`. Add real Supabase and integration credentials only when those services are enabled. Never commit `.env`.

## Run locally

Use two terminals:

```powershell
npm.cmd run dev
```

```powershell
npm.cmd run dev:api
```

- Web: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Quality checks

```powershell
npm.cmd run lint
npm.cmd run build
npm.cmd run lint:api
npm.cmd run typecheck:api
npm.cmd run test:api
```

## Database migrations

After adding or changing SQLAlchemy models:

```powershell
& .\.venv\Scripts\alembic.exe revision --autogenerate -m "describe change"
& .\.venv\Scripts\alembic.exe upgrade head
```

SQLAlchemy/Alembic is the only application database layer. Prisma is intentionally not used. Supabase Auth users will later be linked to application profile records by UUID.

## Known limitations

- APScheduler must run as a single scheduler process and does not provide distributed work queues.
- GitHub ingestion depends on community-maintained Markdown table formats and must fail visibly when schemas change.
- MVP keyword matching can miss nonstandard titles such as “Early Career Program”; ambiguous records remain visible rather than being silently discarded.
- LinkedIn and Indeed are excluded because scraping them creates terms-of-service and reliability risk.
- Source timestamps and completeness vary, so Sprintern records both source time and first-seen time.

## Current scope

This repository currently contains foundation only: a default Next.js application, a minimal FastAPI health endpoint, database connectivity configuration, migrations tooling, and automated checks. Product features have not been implemented.
