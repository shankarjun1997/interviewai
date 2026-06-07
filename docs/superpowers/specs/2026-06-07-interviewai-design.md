# InterviewAI — Architecture & Build Plan

> Status: foundation in progress. Master design doc. Each subsystem gets its own spec/plan/build cycle.

## Vision (condensed)

AI-powered interview assessment platform: JD → AI-generated questions → live transcribed interview with an interviewer-only copilot → weighted scorecard → intelligence report → candidate ranking. Multi-tenant SaaS, any role, technical + non-technical.

## Decomposition

The full vision is ~15 independent subsystems. Build order is dependency-driven:

| # | Subsystem | Depends on | Cycle |
|---|-----------|-----------|-------|
| 0 | **Foundation** (monorepo, data model, auth, tenancy, API contracts) | — | **now** |
| 1 | AI Question Engine (JD/resume → questions + follow-ups) | 0 | 1 |
| 2 | Scoring Framework (role-weighted competency scoring) | 0 | 1 |
| 3 | Live Session + Transcription (WebSocket, Deepgram, diarization) | 0 | 1 |
| 4 | Interviewer Copilot (hints, eval, suggestions) | 1,2,3 | 2 |
| 5 | Intelligence Report (summary, strengths, recommendation) | 2,3 | 2 |
| 6 | Resume Analyzer | 1 | 2 |
| 7 | Candidate Ranking Engine | 2,5 | 2 |
| 8 | Coding Assessment Sandbox (multi-lang exec, plagiarism) | 0 | 3 |
| 9 | Rapid-Fire Mode | 1,2 | 3 |
| 10 | Analytics Dashboard | 2,5,7 | 3 |
| 11 | AI Avatar Assistant | 4 | 3 |
| 12 | Enterprise (SSO, audit, ATS/Slack/Zoom/Meet) | 0 | 4 |
| 13 | Billing / Subscriptions | 0,12 | 4 |
| 14 | Super-Admin console | all | 4 |

## First build cycle = walking skeleton (vertical slice)

One interviewer can: register org → create interview from a JD → AI generates questions → run a live session where candidate audio is transcribed → receive a role-weighted scorecard + summary report.

This forces every architectural layer to exist and proves the design top to bottom.

## Tech stack

- **Frontend:** Next.js (App Router) + TypeScript + Tailwind + shadcn/ui. Dark/light.
- **Backend:** FastAPI (Python 3.11+), async SQLAlchemy 2.0, Pydantic v2.
- **DB:** PostgreSQL. **Cache/pubsub:** Redis. **Realtime:** WebSockets.
- **AI:** provider-abstracted LLM client (Claude default, GPT/Gemini pluggable).
- **Transcription:** provider-abstracted (Deepgram default, AssemblyAI pluggable).
- **Infra:** Docker → Cloud Run / Compute Engine, Cloud SQL, GCS.

## Multi-tenancy model

Shared schema, `organization_id` foreign key on every tenant-scoped row. Row-level isolation enforced in the data-access layer (every query filtered by tenant from the auth context). RBAC roles: `super_admin`, `interviewer`, `candidate`.

## Core data model (Cycle 0)

- **Organization** — tenant root. plan, settings.
- **User** — belongs to org; role enum; auth credentials.
- **Role/Position** — the job being hired for; weighting profile.
- **ScoringProfile** — competency weights (per role; dynamic).
- **Interview** — JD, role, status, schedule, panel.
- **InterviewRound** — ordered rounds within an interview.
- **Question** — generated/curated; type enum; difficulty; links to round.
- **Candidate** — person being interviewed (org-scoped).
- **Session** — a live run of a round; transcript segments; state.
- **TranscriptSegment** — speaker-labeled, timestamped text.
- **Evaluation** — per-answer / per-competency scores.
- **Scorecard** — aggregated weighted result for a candidate+interview.
- **Report** — generated intelligence report artifact.
- **AuditLog** — append-only action log.

## API contract conventions

- REST under `/api/v1`. JSON. Pydantic schemas in `app/schemas`.
- Auth: JWT bearer; tenant + role claims. Dependency `get_current_user`.
- WebSocket: `/api/v1/ws/sessions/{session_id}` — copilot/transcript stream (interviewer-authenticated).
- Errors: RFC-7807-ish `{detail, code}`.

## Security baseline

JWT with short expiry + refresh; bcrypt password hashing; tenant isolation in DAL; role gate on every interviewer/admin route; candidate token scoped to a single session; audit log on mutating actions; secrets via env, never committed.

## Testing

TDD per subsystem. pytest (async) for API; Vitest/Playwright for web. Each subsystem ships with tests before it's "done".
