# Sprintern

**A production-minded internship discovery and alert platform.**

Sprintern turns fragmented internship listings into one focused job feed. Students choose a small
set of role, location, and term preferences; Sprintern normalizes incoming listings, removes
duplicates, matches relevant openings, and delivers Telegram alerts or a daily email digest.

It was built as a portfolio project to demonstrate the decisions behind a reliable full-stack
product: API boundaries, data ownership, asynchronous work, idempotency, authentication, and a
clean interface for an everyday user workflow.

## What users can do

- Browse a unified job board of current internship listings.
- Create focused filters using preset role groups, locations, terms, and exclusions.
- Receive immediate Telegram alerts and a curated daily email digest.
- Save, hide, share, and report postings; track applications from saved through offer or rejection.
- Set notification preferences, quiet hours, channel preferences, and daily limits.
- Export their data or permanently delete their account.

The user experience deliberately does not expose where an individual listing was collected. Source
data remains available only to administrators for ingestion diagnostics and quality control.

## Engineering highlights

- **Independent frontend and backend:** Next.js and FastAPI communicate only through a versioned
  HTTPS REST API. The frontend has no product-database access.
- **Secure data ownership:** Supabase provides identity; FastAPI verifies JWTs on every protected
  request; PostgreSQL row-level security is the final ownership boundary.
- **Reliable background work:** a singleton scheduler writes durable jobs to PostgreSQL; workers
  claim them safely, retry failures with backoff, and prevent duplicate ingestion and delivery.
- **Data quality first:** source records are validated, normalized, deduplicated across repositories,
  and expired when they are no longer useful. A fixed role taxonomy makes filters predictable while
  allowing a job to match multiple relevant categories.
- **Operationally legible:** structured logs include request and correlation IDs, health endpoints
  support deployment checks, and source/parser problems are surfaced for review.

## Architecture

```text
Next.js frontend (Vercel)
        │  REST API + Supabase bearer token
        ▼
FastAPI API (Render) ──────► Supabase PostgreSQL
        │                         │
        ├── GitHub source adapters │ PostgreSQL outbox + durable jobs
        ├── Telegram / Resend       ▼
        └── source administration  scheduler ──► worker(s)
                                           ingestion → matching → notifications
```

| Layer | Responsibility |
| --- | --- |
| `frontend/` | Next.js interface, Supabase sign-in, typed REST client, browser tests |
| `backend/api/routes` | REST resources, validation, HTTP status codes, authorization |
| `backend/api/ingestion` | External-source retrieval, normalization, deduplication, lifecycle tracking |
| `backend/api/matching` | Deterministic classification and explainable filter matching |
| `backend/api/notifications` | Delivery planning, preferences, daily digest, Telegram and Resend adapters |
| `backend/api/scheduler` + `worker` | Singleton scheduling, durable execution, retries, and backoff |

## Technology

- **Frontend:** Next.js, TypeScript, Supabase Auth, Vitest, Playwright
- **Backend:** FastAPI, Pydantic, SQLAlchemy, Alembic, APScheduler
- **Data and operations:** Supabase Postgres, PostgreSQL row-level security, Redis rate limiting,
  Render, Vercel
- **Integrations:** GitHub Contents API, Telegram Bot API, Resend

## Design choices worth discussing

- PostgreSQL is both the transactional source of truth and job queue at this scale. It avoids a
  second queueing system while retaining leases, retries, and idempotency; Redis is reserved for
  distributed rate limits.
- The first matching version is deterministic and explainable. Semantic matching and embeddings are
  intentionally deferred until there is evidence that keyword-based matching is insufficient.
- Email is a curated once-daily channel, not a second instant-alert stream. Telegram is the
  time-sensitive channel; digest ranking keeps inboxes useful rather than noisy.
- Community-maintained Markdown sources are practical for an MVP but can change format. The parser
  rejects unsupported schemas visibly instead of quietly ingesting bad data.

## Local setup

**Requirements:** Node.js 24+, Python 3.12+, Docker Desktop.

```powershell
git clone https://github.com/Pranoym17/Sprintern.git
cd Sprintern

Copy-Item frontend\.env.example frontend\.env.local
Copy-Item backend\.env.example backend\.env

python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
npm.cmd --prefix frontend ci

docker compose -f backend\docker-compose.yml up -d postgres
Set-Location backend
& ..\.venv\Scripts\alembic.exe upgrade head
Set-Location ..
```

Use ignored local environment files for real credentials. Only Supabase's public URL and anon key
belong in the frontend; provider keys, database URLs, internal keys, and service-role credentials
must stay backend-only.

Run each process in its own terminal:

```powershell
# frontend
Set-Location frontend; npm.cmd run dev

# API
Set-Location backend; & ..\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8010

# scheduler
Set-Location backend; & ..\.venv\Scripts\python.exe -m api.scheduler

# worker
Set-Location backend; & ..\.venv\Scripts\python.exe -m api.worker
```

Local URLs: frontend `http://localhost:3000`, API docs `http://localhost:8010/docs`, liveness
`/health/live`, and readiness `/health/ready`.

## Quality checks

```powershell
Set-Location backend
& ..\.venv\Scripts\ruff.exe check api tests migrations scripts
& ..\.venv\Scripts\mypy.exe api scripts
$env:TEST_DATABASE_URL="postgresql+psycopg://sprintern_test:sprintern_test@localhost:5434/sprintern_test"
& ..\.venv\Scripts\pytest.exe -q
Set-Location ..

npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

Database tests require an isolated database ending in `_test`; they will not use the development
or production database. Install Playwright's pinned browser once per computer with
`npx.cmd playwright install chromium` from `frontend/`.

## Deployment overview

- **Vercel:** deploy `frontend/`; configure `NEXT_PUBLIC_API_URL` with the `/api/v1` suffix and
  the public Supabase values.
- **Render:** deploy the API, exactly one scheduler, and one or more workers from `render.yaml`.
  The API pre-deploy step applies Alembic migrations.
- **Supabase:** use separate migration-owner, restricted API, and restricted worker logins. Runtime
  roles must not be database owners, superusers, or able to bypass RLS.
- **Providers:** register Telegram at `/api/v1/webhooks/telegram` and Resend at
  `/api/v1/webhooks/resend`. Resend is used for outbound delivery telemetry only, not inbound mail.

Before launch, configure explicit CORS/host settings, Redis-backed rate limits, production OAuth
redirects, SPF/DKIM/DMARC, backups, secret scanning, and monitoring for readiness, scheduler
heartbeat, source freshness, failed jobs, and delivery bounces.

## Current limitations

- Current sources are GitHub-hosted internship trackers. Additional first-party ATS sources are a
  planned expansion.
- Matching is deterministic, so unusually named roles can be missed or categorized as “Other
  technical.”
- A Telegram delivery has a narrow at-least-once duplicate window if Telegram accepts a message
  immediately before a database failure.
- Application caching, AI classification, embeddings, and recommendations are intentionally not
  part of the current release.

## License

This project is intended as a personal portfolio project. Do not redistribute provider credentials
or scraped source data.
