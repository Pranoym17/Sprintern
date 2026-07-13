# Sprintern

Internship alert aggregator. The foundation uses Next.js for the web app, FastAPI for the API and background work, and PostgreSQL for application data. Docker PostgreSQL is used locally; Supabase PostgreSQL and Auth are intended for production.

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

## Current scope

This repository currently contains foundation only: a default Next.js application, a minimal FastAPI health endpoint, database connectivity configuration, migrations tooling, and automated checks. Product features have not been implemented.
