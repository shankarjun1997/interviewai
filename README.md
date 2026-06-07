# InterviewAI

AI-powered interview assessment platform. Monorepo.

```
apps/
  api/   FastAPI backend (async SQLAlchemy, JWT auth, multi-tenant)
  web/   Next.js frontend (App Router, Tailwind)
packages/shared/   shared types/contracts
infra/             docker-compose, deployment
docs/superpowers/specs/   design docs (see the master architecture doc)
```

## What works today (walking skeleton)

Register an org → create an interview from a job description → AI-generates
role/JD-aware questions → tenant-isolated, role-gated API. Runs fully offline
(sqlite + stub LLM) with no API keys; set `ANTHROPIC_API_KEY` for real generations.

## Run the backend

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload      # http://localhost:8000  (/docs for OpenAPI)
pytest                             # walking-skeleton smoke test
```

## Run the frontend

```bash
cd apps/web
npm install
npm run dev                        # http://localhost:3000
```

## Full stack (Postgres + Redis)

```bash
cd infra && docker compose up
```

## Build order

See `docs/superpowers/specs/2026-06-07-interviewai-design.md` — the master design
doc with the 15-subsystem decomposition and dependency-ordered build plan.
Cycle 0 (foundation) + the question engine are in place; remaining subsystems
build against the contracts in `apps/api/app/services/llm.py` and the data model
in `apps/api/app/models/`.
```
