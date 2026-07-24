# Sprintern

Sprintern monitors internship listings, deduplicates them, matches them to student filters, and
sends controllable Telegram and email alerts. The current product uses GitHub-hosted internship
repositories, deterministic matching, an application tracker, source administration, and a
responsive Next.js workspace.

## Architecture

The frontend and backend are independent deployable projects:

```text
frontend/ (Next.js on Vercel)
    |
    | HTTPS REST + Supabase bearer token
    v
backend/ (FastAPI on Render)
    |
    +--> Supabase PostgreSQL
    +--> Resend / Telegram / GitHub

singleton scheduler --> PostgreSQL background_jobs --> worker(s)
                                               |
                                               +--> ingestion --> matching --> notification outbox
```

- `frontend/` has no database client and never imports backend code. Supabase is used only for
  authentication; all product data crosses the versioned REST API.
- `backend/api/routes` owns HTTP translation and typed Pydantic contracts.
- `backend/api/ingestion` validates, normalizes, deduplicates, and records source data.
- `backend/api/matching` creates explainable deterministic matches.
- `backend/api/notifications` plans idempotent deliveries and sends the PostgreSQL outbox.
- `backend/api/scheduler` only enqueues due work.
- `backend/api/worker` claims leased jobs with `FOR UPDATE SKIP LOCKED`, retries failures with
  exponential backoff, and dead-letters exhausted work.

The public contract is `/api/v1/...`; internal operations use `/internal/v1/...` and an independent
internal key. Health endpoints remain unversioned for hosting platforms.

Ingestion origins remain hidden from regular users. Repository identities and parser diagnostics are
an intentional exception available only to Supabase-authenticated administrators in the source
control room; they never appear in public job, match, export, email, or Telegram payloads. The
generated frontend contract excludes `/internal/v1` entirely.

### Important tradeoffs

- SQLAlchemy/Alembic is the only application database layer; Prisma would duplicate models and
  migrations.
- Supabase owns identity while FastAPI validates every JWT and authorizes every request.
- API requests use a restricted PostgreSQL login plus transaction-local user claims, so RLS
  independently enforces ownership. Background processes use a separate worker login.
- PostgreSQL is both the source of truth and durable job queue at this scale. Redis is used only for
  distributed rate-limit state. Application/response caching is deliberately deferred.
- Keyword matching ships before paid or nondeterministic AI classification.
- Community Markdown sources can drift, so unsupported tables fail visibly and create parser alerts.

## Project layout

```text
frontend/                 Next.js app, tests, frontend Dockerfile and env example
backend/                  FastAPI app, migrations, worker, scheduler and backend env example
.github/workflows/        independent frontend and backend CI pipelines
render.yaml               three independent backend services
```

## Local setup

Requirements: Node.js 24+, Python 3.12+, Docker Desktop.

```powershell
git clone YOUR_REPOSITORY_URL
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

Configure real local credentials only in ignored env files. The browser may contain only
`NEXT_PUBLIC_SUPABASE_URL` and the public anon/publishable key. Never put the service-role key,
database URLs, provider keys, or internal key in `frontend/`.

Backend configuration precedence is:

1. process environment;
2. `.env.<APP_ENV>.local`;
3. `.env.<APP_ENV>`;
4. `.env`.

Env files are loaded only for local, development, and test. Staging and production accept process
environment variables only. Production startup rejects debug/docs mode, wildcard or HTTP CORS,
owner database credentials, missing Redis rate limiting, and weak operational secrets.

Next.js follows its standard environment precedence. `NEXT_PUBLIC_*` values are embedded at build
time, so Vercel must have the correct environment-specific API and Supabase public values before
building.

## Run locally

Use four terminals:

```powershell
Set-Location frontend
npm.cmd run dev
```

```powershell
Set-Location backend
& ..\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8010
```

```powershell
Set-Location backend
& ..\.venv\Scripts\python.exe -m api.scheduler
```

```powershell
Set-Location backend
& ..\.venv\Scripts\python.exe -m api.worker
```

- Web: `http://localhost:3000`
- API docs: `http://localhost:8010/docs`
- Liveness: `http://localhost:8010/health/live`
- Readiness: `http://localhost:8010/health/ready`

The scheduler does not perform provider work. It creates idempotent jobs; the worker must be running
for ingestion, matching, and automatic dispatch.

## Database roles and RLS

Alembic creates the `sprintern_api` and `sprintern_worker` NOLOGIN roles and grants their minimum
table privileges. Create independent login roles as the database owner, using passwords generated
by your secret manager:

```sql
CREATE ROLE sprintern_api_login LOGIN PASSWORD 'GENERATE_A_UNIQUE_PASSWORD';
CREATE ROLE sprintern_worker_login LOGIN PASSWORD 'GENERATE_A_DIFFERENT_PASSWORD';
GRANT sprintern_api TO sprintern_api_login;
GRANT sprintern_worker TO sprintern_worker_login;
```

Set:

- `DATABASE_URL` to the migration-owner URL, used only by Alembic/pre-deploy migration.
- `DATABASE_API_URL` to `sprintern_api_login`.
- `DATABASE_WORKER_URL` to `sprintern_worker_login`.

Do not grant `BYPASSRLS`, superuser, or table-owner privileges to either runtime login. User sessions
set `request.jwt.claim.sub` transaction-locally on every transaction; RLS policies then restrict
profiles, filters, matches, applications, and notification data to that UUID.

## API behavior and reliability

- Every JSON endpoint has typed request/response schemas.
- Errors use `{"error":{"code","message","request_id","details"}}`.
- All responses include `X-Request-ID`; valid incoming IDs are preserved.
- CORS uses explicit origins and methods. Trusted proxy headers are honored only from configured
  networks.
- Public API traffic has an IP safety limit. Sensitive mutations also have per-user limits.
- Production uses Redis for rate-limit coordination across API instances; it is not a product cache.
- Provider calls have bounded timeouts. Source GETs retry transient failures and honor
  `Retry-After`; notification retries are persisted in the outbox.
- Source records are validated with strict Pydantic models, length-bounded, cleaned of control
  characters, and URL-validated before persistence.
- Stable job, source, match, delivery, and background-job keys prevent duplicate work.

## Quality checks

```powershell
Set-Location backend
& ..\.venv\Scripts\ruff.exe check api tests migrations scripts
& ..\.venv\Scripts\mypy.exe api scripts
& ..\.venv\Scripts\pytest.exe -q
Set-Location ..

npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

Install Playwright's pinned browser once on each computer:

```powershell
Set-Location frontend
$env:PLAYWRIGHT_BROWSERS_PATH="0"
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

CI runs frontend and backend workflows independently and builds each Docker image from only its own
project directory.

## Deployment

### Frontend — Vercel

1. Import the repository and set the Root Directory to `frontend`.
2. Keep the detected Next.js build settings.
3. Configure `NEXT_PUBLIC_API_URL=https://YOUR_API_HOST/api/v1`,
   `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `PUBLIC_API_URL`, and the public
   support email.
4. Add production and preview URLs to Supabase Auth redirect allowlists.
5. Deploy only after the backend readiness endpoint is healthy.

The frontend builds without a running backend. Unit tests mock HTTP at the client boundary.

### Backend — Render

`render.yaml` defines:

- one API web service with `/health/ready`;
- exactly one scheduler worker;
- one or more durable background workers.

Create the `sprintern-backend` environment group values marked `sync: false`. Use one migration-owner
URL and separate restricted runtime URLs. Configure Redis for rate limiting, explicit production
CORS/hosts/proxy CIDRs, Supabase, GitHub, Telegram, Resend, Sentry, admin IDs, and strong independent
internal/unsubscribe/webhook secrets. The API pre-deploy command applies migrations.

Register Telegram's webhook as:

```text
https://YOUR_API_HOST/api/v1/webhooks/telegram
```

Register Resend's send-event webhook as:

```text
https://YOUR_API_HOST/api/v1/webhooks/resend
```

Sprintern sends email only; it never receives mailbox messages. Resend webhook events are delivery,
bounce, and complaint telemetry.

## Observability and operations

API, scheduler, and worker logs are structured JSON with request/job/correlation IDs. Secret-like
fields and configured credentials are redacted; request bodies are never logged. Sentry is optional
through `ERROR_TRACKING_DSN`, with PII and request bodies disabled.

Monitor:

- `/health/live` for process uptime and `/health/ready` for DB/migration readiness;
- `/internal/v1/monitoring/status` for scheduler freshness, source/parser failures, database
  capacity, Resend events, and GitHub limit warnings;
- dead `background_jobs` and failed notification deliveries;
- scheduler heartbeat age and source freshness;
- Resend bounces/complaints and PostgreSQL capacity/backups.

Alert if readiness fails, the scheduler heartbeat is stale, dead jobs appear, a parser produces zero
accepted rows, or a source becomes stale. A provider outage degrades that provider's job and retries;
it does not stop other sources or the API.

## Security launch checklist

- Rotate all development credentials ever pasted into terminals, chat, screenshots, or logs.
- Search the full Git history with GitHub secret scanning and a local scanner such as Gitleaks.
- Keep all `.env*` files ignored except the two dummy `.env.example` files.
- Enable GitHub secret scanning, push protection, and Dependabot.
- Restrict GitHub tokens to read-only repository contents and Resend keys to the sending domain.
- Keep Supabase service-role credentials backend-only; verify RLS with two real users.
- Configure SPF, DKIM, DMARC, custom SMTP/OAuth redirects, backups, uptime alerts, and support email.
- Run the staging acceptance script and manually verify signup, filter, match, email, Telegram,
  application tracking, export, deletion, cross-user denial, and duplicate suppression.

## Known limitations

- Community GitHub tables can change without notice; parser alerts require an operator response.
- Matching is deterministic keyword-based and can miss unusual role titles.
- Telegram cannot provide a general provider idempotency key, leaving a very small at-least-once
  duplicate window if Telegram accepts a message immediately before a database failure.
- PostgreSQL queue polling is appropriate for current scale; a dedicated broker can replace it when
  throughput or scheduling complexity proves the need.
- Application caching, AI semantic search, embeddings, and recommendations remain intentionally
  deferred.
