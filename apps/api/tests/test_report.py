"""Tests for the Candidate Intelligence Report subsystem. Runs fully offline
(sqlite + stub LLM). Fresh sqlite DB per test; tables created via
Base.metadata.create_all after importing app.models.

The reports router is mounted on a dedicated FastAPI app here because main.py is
not edited by this subsystem; production wires it via app.include_router.
"""
import asyncio
import os

import pytest

# Must be set before app.db.base imports (engine binds to this URL once).
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_report.db")

from app.services.llm import StubClient  # noqa: E402
from app.services.report import (  # noqa: E402
    RECOMMENDATIONS,
    generate_report,
)


@pytest.fixture(autouse=True)
def _fresh_db():
    # The async engine binds to DATABASE_URL at import time, so we get a fresh
    # schema per test by dropping and recreating all tables rather than swapping
    # the file. Effectively a clean sqlite state for every test.
    async def _reset():
        import app.models  # noqa: F401  (register tables on Base.metadata)
        from app.db.base import Base, engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())
    yield


def _make_app():
    from fastapi import FastAPI

    from app.api import report

    app = FastAPI()
    app.include_router(report.router)
    return app


def _client(app):
    from httpx import ASGITransport, AsyncClient

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_tables():
    import app.models  # noqa: F401  (register tables on Base.metadata)
    from app.db.base import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


def _token(*, role="interviewer", org_id="org-1", user_id="user-1"):
    from app.core.security import create_access_token

    return create_access_token(user_id=user_id, org_id=org_id, role=role)


# --------------------------------------------------------------------------
# Service-level unit tests (no HTTP)
# --------------------------------------------------------------------------

def test_stub_report_is_well_formed():
    async def run():
        content = await generate_report(
            StubClient(),
            interview_title="Senior Backend Engineer",
            job_description="Python, async, distributed systems",
            transcript=[
                {"speaker": "interviewer", "text": "Tell me about a hard bug.", "start_ms": 0},
                {"speaker": "candidate", "text": "I once debugged a race condition.", "start_ms": 1000},
            ],
            evaluations=[
                {"competency": "technical", "score": 82.0, "rationale": "Strong systems grasp"},
                {"competency": "communication", "score": 40.0, "rationale": "Rambling answers"},
            ],
            scorecard={
                "overall_score": 74.0,
                "competency_scores": {"technical": 82, "communication": 40},
                "recommendation": "hire",
            },
        )
        return content

    content = asyncio.run(run())
    # All required keys present.
    for key in (
        "executive_summary",
        "strengths",
        "weaknesses",
        "risk_indicators",
        "recommended_position",
        "interview_highlights",
        "notable_quotes",
        "role_match_percent",
    ):
        assert key in content, f"missing {key}"

    assert content["recommended_position"] in RECOMMENDATIONS
    assert content["executive_summary"].count("\n\n") == 2  # exactly 3 paragraphs
    assert len(content["strengths"]) <= 10
    assert len(content["weaknesses"]) <= 10
    assert 0 <= content["role_match_percent"] <= 100
    # candidate quote captured, interviewer line excluded
    assert any("race condition" in q for q in content["notable_quotes"])
    assert content["recommended_position"] == "hire"


def test_stub_report_handles_empty_inputs():
    async def run():
        return await generate_report(
            StubClient(),
            interview_title="Empty",
            job_description="",
            transcript=[],
            evaluations=[],
            scorecard=None,
        )

    content = asyncio.run(run())
    assert content["recommended_position"] == "reject"  # score 0
    assert content["role_match_percent"] == 0
    assert content["strengths"] == []
    assert content["executive_summary"]


# --------------------------------------------------------------------------
# HTTP endpoint tests
# --------------------------------------------------------------------------

async def _seed_interview(engine, *, org_id="org-1"):
    """Insert an interview with a session, transcript, evals, scorecard."""
    from app.db.base import SessionLocal
    from app.models import (
        Evaluation,
        Interview,
        Scorecard,
        Session as SessionModel,
        TranscriptSegment,
    )

    async with SessionLocal() as db:
        iv = Interview(
            organization_id=org_id,
            created_by="user-1",
            title="Data Engineer",
            job_description="Spark, dbt",
            difficulty="hard",
        )
        db.add(iv)
        await db.flush()
        sess = SessionModel(interview_id=iv.id, status="completed")
        db.add(sess)
        await db.flush()
        db.add_all(
            [
                TranscriptSegment(
                    session_id=sess.id, speaker="candidate",
                    text="I built a streaming pipeline.", start_ms=100, end_ms=200,
                ),
                TranscriptSegment(
                    session_id=sess.id, speaker="interviewer",
                    text="Nice, tell me more.", start_ms=200, end_ms=300,
                ),
            ]
        )
        db.add_all(
            [
                Evaluation(session_id=sess.id, competency="technical", score=88.0, rationale="Deep"),
                Evaluation(session_id=sess.id, competency="communication", score=70.0, rationale="Clear"),
            ]
        )
        db.add(
            Scorecard(
                interview_id=iv.id, overall_score=86.0,
                competency_scores={"technical": 88, "communication": 70},
                recommendation="strong_hire",
            )
        )
        await db.commit()
        return iv.id


def test_generate_and_get_report_endpoint():
    async def run():
        engine = await _create_tables()
        iv_id = await _seed_interview(engine)
        app = _make_app()
        h = {"Authorization": f"Bearer {_token()}"}
        async with _client(app) as c:
            r = await c.post(f"/api/v1/reports/interviews/{iv_id}/generate", headers=h)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["interview_id"] == iv_id
            assert body["recommended_position"] == "strong_hire"
            assert body["executive_summary"]
            assert any("streaming pipeline" in q for q in body["notable_quotes"])

            # GET returns the persisted report
            r = await c.get(f"/api/v1/reports/interviews/{iv_id}", headers=h)
            assert r.status_code == 200, r.text
            assert r.json()["id"] == body["id"]

            # regenerate upserts (same interview -> same report id)
            r2 = await c.post(f"/api/v1/reports/interviews/{iv_id}/generate", headers=h)
            assert r2.status_code == 200, r2.text
            assert r2.json()["id"] == body["id"]
        await engine.dispose()

    asyncio.run(run())


def test_get_report_404_when_not_generated():
    async def run():
        engine = await _create_tables()
        iv_id = await _seed_interview(engine)
        app = _make_app()
        h = {"Authorization": f"Bearer {_token()}"}
        async with _client(app) as c:
            r = await c.get(f"/api/v1/reports/interviews/{iv_id}", headers=h)
            assert r.status_code == 404, r.text
        await engine.dispose()

    asyncio.run(run())


def test_tenant_isolation_blocks_other_org():
    async def run():
        engine = await _create_tables()
        iv_id = await _seed_interview(engine, org_id="org-1")
        app = _make_app()
        # token scoped to a different org
        h = {"Authorization": f"Bearer {_token(org_id='org-2')}"}
        async with _client(app) as c:
            r = await c.post(f"/api/v1/reports/interviews/{iv_id}/generate", headers=h)
            assert r.status_code == 404, r.text  # not visible cross-tenant
        await engine.dispose()

    asyncio.run(run())


def test_requires_auth():
    async def run():
        engine = await _create_tables()
        iv_id = await _seed_interview(engine)
        app = _make_app()
        async with _client(app) as c:
            r = await c.post(f"/api/v1/reports/interviews/{iv_id}/generate")
            assert r.status_code == 401, r.text
        await engine.dispose()

    asyncio.run(run())


def test_role_gate_rejects_candidate():
    async def run():
        engine = await _create_tables()
        iv_id = await _seed_interview(engine)
        app = _make_app()
        h = {"Authorization": f"Bearer {_token(role='candidate')}"}
        async with _client(app) as c:
            r = await c.post(f"/api/v1/reports/interviews/{iv_id}/generate", headers=h)
            assert r.status_code == 403, r.text
        await engine.dispose()

    asyncio.run(run())
