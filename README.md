# Sprintern

Internship alert aggregator. The foundation uses Next.js for the web app, FastAPI for the API and background work, and PostgreSQL for application data. Docker PostgreSQL is used locally; Supabase PostgreSQL and Auth are intended for production.

## Problem and MVP

Internship listings can receive a large number of applications within hours. Sprintern polls structured job sources, normalizes and deduplicates listings, matches them to a student's saved preferences, and delivers Telegram or email alerts.

The current product ingests GitHub-hosted internship repositories, performs deterministic matching,
supports a full application tracker, and sends controllable Telegram and email alerts. AI
classification, embeddings, SMS, and auto-apply remain deliberately deferred.

## Architecture

```text
Next.js ── bearer token ──> FastAPI ── SQLAlchemy ──> PostgreSQL
   │                            │                       local: Docker
   └── Supabase Auth            ├── ingestion          prod: Supabase
                                ├── matching
APScheduler ── workflows ───────└── notifications ──> Telegram / Resend
```

Backend responsibilities are intentionally separated:

FastAPI and APScheduler run as separate processes. FastAPI serves HTTP and Telegram webhooks;
the scheduler owns polling and due-delivery dispatch. Both reuse the same application services
and PostgreSQL state.

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
- PostgreSQL advisory locks permit exactly one scheduler process and prevent manual ingestion from
  overlapping scheduled ingestion for the same source.
- Keyword matching ships before AI so the end-to-end system is measurable before adding cost and nondeterminism.
- pgvector will live in PostgreSQL rather than a separate vector database because expected data volume does not justify another service.

### Frontend decisions

- Marketing content stays server-rendered while authentication and mutations use narrow client
  component boundaries. This keeps the landing page fast without making the interactive workspace
  harder to follow.
- Supabase manages browser sessions and refresh cookies. Next.js performs optimistic route gating,
  but FastAPI still validates every bearer token and remains the authorization boundary.
- One typed API client owns bearer headers, cursor encoding, empty responses, and error
  normalization. Pages do not duplicate raw fetch behavior.
- The UI exposes only backend-supported match states: matched, applied, and dismissed. Saved and
  unread states are intentionally not implied before their data model exists.
- The interface uses a small custom component system instead of a large UI library. At this MVP
  size, accessible native controls and shared CSS tokens are easier to audit and explain.

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

For Supabase Auth, create a project with asymmetric JWT signing keys, then set `SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, and the publishable/anon keys. FastAPI downloads the project's JWKS, caches it for at most ten minutes, and validates token signature, issuer, audience, expiry, and subject. Secret and service-role keys must never be exposed to the browser.

The browser also needs the public API address:

```dotenv
NEXT_PUBLIC_API_URL=http://127.0.0.1:8010
```

For deployment, set `APP_ENV=production` and use an HTTPS `NEXT_PUBLIC_API_URL`. Production startup
fails when the public API URL is missing, malformed, or insecure, preventing a successful build that
would accidentally call each user's localhost. The Next.js layer also sends CSP, anti-framing,
content-type, referrer, permissions, and HSTS headers.

In Supabase Authentication URL Configuration, use `http://localhost:3000` as the local site URL
and allow `http://localhost:3000/auth/callback` as a redirect URL. Only the anon/publishable key is
safe in a `NEXT_PUBLIC_` variable; never use a service-role key in the frontend.

The auth screen offers Google as the fastest path. To enable it, configure the Google provider in
Supabase Authentication, add the Supabase callback URL shown there to the Google OAuth client, and
keep `http://localhost:3000/auth/callback` in the Supabase redirect allowlist. Email/password remains
available when Google is not configured. Password recovery uses the same callback allowlist and
exchanges a short-lived Supabase recovery session before accepting a new password.

## Run locally

Use three terminals for the full application:

```powershell
npm.cmd run dev
```

```powershell
npm.cmd run dev:api
```

```powershell
& .\.venv\Scripts\python.exe -m api.scheduler
```

- Web: http://localhost:3000
- API: http://localhost:8010
- API docs: http://localhost:8010/docs
- Health: http://localhost:8010/health

The frontend includes:

- An accessible, responsive product landing page
- Supabase sign-up, sign-in, confirmation callback, session refresh, and protected routes
- Overview analytics and recent matches
- Cursor-paginated match review with applied, dismissed, and restore actions
- Filter creation, editing, activation, pausing, and deletion
- Profile cadence, timezone, email preference, and Telegram link management
- A warm-neutral and signal-coral visual system with Urbanist headings and Inter body text
- Chip-based filter setup, browser-local new-match cues, relative posting times, skeleton feeds,
  optimistic applied status, and one-click undo
- Guided first-run filter/channel setup and password recovery
- Desktop sidebar and mobile bottom navigation with reduced-motion support

## Quality checks

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test
npm.cmd run test:e2e
npm.cmd run build
npm.cmd run lint:api
npm.cmd run typecheck:api
npm.cmd run test:api
```

Backend HTTP and scheduler logs are structured JSON. Every API response receives an
`X-Request-ID`; a valid caller-provided ID is preserved for cross-service tracing. Logs intentionally
exclude request bodies and query strings and redact configured credentials and common secret fields.
Unexpected failures return a stable generic response while retaining only safe operational context.

### Why Playwright installs Chromium separately

`@playwright/test` provides the test runner and browser-control code, but it does not assume that a
compatible browser binary already exists. Chrome installed on the computer may be a different
version, have user extensions, or update independently and make tests inconsistent. On each new
computer or fresh clone, install dependencies and then download Playwright's pinned Chromium build:

```powershell
npm.cmd install
$env:PLAYWRIGHT_BROWSERS_PATH="0"
npx.cmd playwright install chromium
```

`PLAYWRIGHT_BROWSERS_PATH=0` stores that browser under this project's `node_modules` tree instead of
the user's shared Playwright cache. The committed `test:e2e` script uses the same location, making
the selected browser deterministic. The binary is ignored by Git. Run the installation once per
fresh dependency installation, and again only when a Playwright upgrade requests a newer browser.
It is not required before every test run.

## Database migrations

After adding or changing SQLAlchemy models:

```powershell
& .\.venv\Scripts\alembic.exe revision --autogenerate -m "describe change"
& .\.venv\Scripts\alembic.exe upgrade head
```

SQLAlchemy/Alembic is the only application database layer. Prisma is intentionally not used. Supabase Auth users will later be linked to application profile records by UUID.

## Implemented API foundation

- Supabase bearer-token verification through asymmetric JWKS
- Idempotent application-profile bootstrap
- Profile and filter resources with ownership enforcement
- Active job feed and stable cursor pagination
- Match status and basic analytics resources
- Status-filtered match pagination with authoritative matched/applied/dismissed totals
- Standard validation and application error bodies
- Service-key-protected source status endpoint

The shared ingestion framework defines typed adapter contracts, normalized job candidates, URL/text canonicalization, cross-source deduplication, 30-day repost handling, retry/backoff behavior, per-source non-overlap locks, durable run counters, and transactional cursor updates.

## MVP ingestion, matching, and notifications

Implemented source adapters:

- Greenhouse complete board snapshots with HTML cleanup
- Lever global and EU tenants with safe pagination
- RemoteOK with required source attribution metadata
- GitHub internship repositories with commit-SHA cursors and defensive Markdown-table parsing

Complete snapshots drive job lifecycle conservatively. A source occurrence is stale after two successful snapshots omit it and expired after three. Partial, incremental, failed, and suspiciously empty snapshots never advance absence counters. A canonical job stays active while any attached source remains active. Reuse of an expired external ID after 30 days creates a new occurrence rather than silently reviving an old application cycle.

Keyword matching first classifies whether a listing is clearly an internship. Confirmed jobs use AND semantics across role, location, term, and work mode, with OR semantics inside each keyword list and across a user's filters. Empty dimensions are unrestricted. Ambiguous listings remain in the general feed but do not create matches or notifications. Match reasons include the filter, matched dimensions, and matcher version.

Notifications use a PostgreSQL outbox. Email and Telegram delivery rows are created transactionally with matches, claimed using `FOR UPDATE SKIP LOCKED`, and retried with bounded backoff. Hourly and daily deliveries are grouped into digests. Resend receives a stable idempotency key; Telegram uses plain text plus an apply button. Telegram accounts are linked through short-lived, single-use tokens stored only as hashes.

Notification dispatch can also be exercised manually for operations and troubleshooting:

```http
POST /internal/notifications/dispatch
X-Internal-API-Key: your-internal-key
```

## Source administration and scheduling

The database is the runtime source registry. An allowlisted Supabase administrator can add, edit,
preview, enable, disable, test, and ingest GitHub repositories at `/admin/sources`; every change is
audited. Preview is read-only and must succeed before a source can be enabled. The scheduler
reconciles database changes without a restart.

`config/sources.toml` remains a non-secret first-run seed and disaster-recovery fallback. It is
loaded only when the source registry is empty or unavailable. Provider tokens remain in `.env`.

```toml
[[github]]
enabled = true
owner = "vanshb03"
repository = "Summer2027-Internships"
path = "README.md"
branch = "dev"
term = "Summer 2027"
poll_minutes = 15
jitter_seconds = 30
```

Configuration is strict: unknown fields, duplicate source identities, missing required values, and
invalid intervals are rejected. Source identity is owner, repository, and path; two branches for
that same identity are rejected because their cursors would collide.

Scheduler environment settings have conservative defaults:

```dotenv
SCHEDULER_SOURCE_CONFIG=config/sources.toml
SCHEDULER_NOTIFICATION_INTERVAL_SECONDS=30
SCHEDULER_HEARTBEAT_INTERVAL_SECONDS=30
SCHEDULER_TIMEZONE=UTC
SCHEDULER_MISFIRE_GRACE_SECONDS=60
SCHEDULER_SHUTDOWN_TIMEOUT_SECONDS=30
SCHEDULER_SOURCE_SYNC_SECONDS=60
```

Run the scheduler from the repository root so the relative configuration path resolves:

```powershell
& .\.venv\Scripts\python.exe -m api.scheduler
```

Each enabled GitHub repository receives one interval job with a stable ID, jitter, coalescing, and
`max_instances=1`. Unchanged commit SHAs are no-ops. Failed sources receive persisted exponential
backoff capped at one hour. Notification dispatch runs independently every 30 seconds, so a source
failure does not prevent already-due alerts from being delivered.

The process handles Ctrl+C and termination signals, pauses new jobs, gives active workflows a
bounded time to finish, records a clean stop, and closes its HTTP client. Starting FastAPI never
starts APScheduler as an import side effect.

Scheduler health is protected by the internal service key:

```http
GET /internal/scheduler/status
X-Internal-API-Key: your-internal-key
```

The response is `unknown` before the first run, `healthy` while heartbeats are recent, `stale`
after heartbeats stop unexpectedly, and `stopped` after clean shutdown. It exposes only non-secret
job IDs and next-run timestamps. Source results remain at `GET /internal/sources/status`.

### Scheduler troubleshooting

| Symptom | Check |
| --- | --- |
| Scheduler exits immediately | Validate `config/sources.toml`, database connectivity, and migrations. |
| Another scheduler is running | Stop it; exactly one scheduler process is supported. |
| Source is skipped | Inspect `backoff_until` and `last_error` in `/internal/sources/status`. |
| Poll succeeds with zero jobs | An unchanged GitHub commit is an expected no-op. |
| No Telegram alert | Confirm a match and pending delivery exist, the profile is linked/enabled, and the token is current. |
| Status is stale | Restart the scheduler and inspect its logs; FastAPI remains independent. |

## Notification controls

Profile settings provide email, Telegram, cadence, timezone, quiet hours, weekend pause, daily
caps, and consent defaults. Individual filters can override channel, cadence, and priority.
Supported cadences are instant, hourly, daily, and weekly. When multiple filters match one job,
Sprintern creates at most one delivery per channel, merges match reasons, selects the highest
priority and earliest permitted cadence, and still applies quiet-time and cap rules.

Test sends are rate-limited, clearly labelled, and do not require or modify a real match. Telegram
supports `/pause`, `/resume`, `/status`, `/filters`, and `/help` only for linked chats. Resend is a
send-only integration: `/webhooks/resend` accepts signed delivery, bounce, complaint, and
suppression events; Sprintern does not receive mailbox email.

## Launch hardening

The production Compose topology defines one API process, exactly one scheduler, and one standalone
Next.js frontend. PostgreSQL row-level security policies provide a second boundary for user-owned
data; FastAPI ownership checks remain authoritative. Sentry can collect API and scheduler errors
without request bodies or default PII.

Protected operational endpoints:

- `GET /internal/launch/readiness` lists incomplete external launch controls without exposing values.
- `GET /internal/monitoring/status` reports scheduler, source, parser, Resend event, database
  capacity, and GitHub API-limit signals.

Build and inspect the production containers locally:

```powershell
docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml up -d
```

Run the reversible two-user staging smoke test after deployment:

```powershell
& .\.venv\Scripts\python.exe scripts/staging_acceptance.py
```

The script checks health, auth, filter creation, cross-user denial, matches, export, optional test
notifications, monitoring, and cleanup. Receipt, application links, reminders, and destructive
account deletion remain explicit manual acceptance steps.

## Known limitations

- APScheduler must run as a single scheduler process and does not provide distributed work queues.
- The scheduler is intentionally a singleton; PostgreSQL advisory locking rejects a second owner.
- Synchronous SQLAlchemy work is acceptable at current polling volume but would move behind a
  queue or async worker boundary at substantially higher concurrency.
- GitHub ingestion depends on community-maintained Markdown table formats and must fail visibly when schemas change.
- MVP keyword matching can miss nonstandard titles such as “Early Career Program”; ambiguous records remain visible rather than being silently discarded.
- LinkedIn and Indeed are excluded because scraping them creates terms-of-service and reliability risk.
- Source timestamps and completeness vary, so Sprintern records both source time and first-seen time.
- Notification delivery is at-least-once. A provider may accept a message immediately before a database failure; Resend idempotency reduces this duplicate window, while Telegram offers no equivalent general key.

## Current scope

The codebase now includes the product data foundation, discovery and tracker workflows, advanced
filters, per-filter notification controls, database-backed source administration, RLS, deployment
containers, operational readiness and monitoring endpoints, and automated staging support.
Production domains, DNS records, OAuth credentials, hosted monitors, backup configuration,
credential rotation, and the actual deployment remain owner-operated external actions.
