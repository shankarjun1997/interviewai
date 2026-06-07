"""Tests for the AI Resume Analyzer subsystem. Runs fully offline (sqlite +
stub LLM): register -> analyze ad-hoc resume -> analyze with candidate_id."""
import asyncio
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_resume.db")
# Force the deterministic stub client (no API key) for reproducible assertions.
os.environ["LLM_PROVIDER"] = "stub"

RESUME = """\
Jane Doe
Senior Software Engineer at Acme Corp

Experienced engineer with 6 years building backend systems in Python and Go.
Skills: Python, FastAPI, PostgreSQL, Docker, Kubernetes, AWS, Kafka

Projects
Realtime analytics pipeline using Kafka and Spark
Internal developer platform on Kubernetes

Certifications
AWS Certified Solutions Architect
"""

JD = "Looking for a backend engineer with Python, FastAPI, Terraform and GCP."


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


def _client():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    # The resume router lives in its own module; ensure it is mounted even if
    # app.main has not been updated to include it yet. Idempotent: skip if
    # already present (e.g. once the include line is added to app.main).
    from app.api import resume as resume_api

    if not any(getattr(r, "path", "") == "/api/v1/resume/analyze" for r in app.routes):
        app.include_router(resume_api.router)

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register(c):
    r = await c.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Acme",
            "email": "lead-resume@acme.com",
            "password": "supersecret",
            "full_name": "Lead",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _run_flow():
    import app.models  # noqa: F401  (register tables on Base.metadata)
    from app.db.base import Base, SessionLocal, engine
    from app.models import Candidate

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _client() as c:
        auth = await _register(c)
        org_id = auth["organization_id"]
        h = {"Authorization": f"Bearer {auth['access_token']}"}

        # 1) auth required
        r = await c.post("/api/v1/resume/analyze", json={"resume_text": RESUME})
        assert r.status_code == 401, r.text

        # 2) ad-hoc analysis (no candidate_id) with JD -> missing skills surfaced
        r = await c.post(
            "/api/v1/resume/analyze",
            headers=h,
            json={"resume_text": RESUME, "job_description": JD},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["source"] == "stub"
        assert data["persisted"] is False
        assert data["candidate_id"] is None
        assert "python" in data["skills"]
        assert "fastapi" in data["skills"]
        # JD wants terraform + gcp, resume lacks them
        assert "terraform" in data["missing_skills"]
        assert "gcp" in data["missing_skills"]
        # well-formed plan/questions/certs
        assert len(data["interview_plan"]) >= 1
        assert len(data["suggested_questions"]) >= 1
        assert any("AWS" in cert for cert in data["certifications"])

        # 3) seed a candidate, then analyze with candidate_id -> persists resume
        async with SessionLocal() as s:
            cand = Candidate(
                organization_id=org_id, full_name="Jane Doe", email="jane@x.com"
            )
            s.add(cand)
            await s.commit()
            cand_id = cand.id

        r = await c.post(
            "/api/v1/resume/analyze",
            headers=h,
            json={"resume_text": RESUME, "candidate_id": cand_id},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["persisted"] is True
        assert data["candidate_id"] == cand_id

        async with SessionLocal() as s:
            refreshed = await s.get(Candidate, cand_id)
            assert refreshed.resume_text == RESUME

        # 4) unknown candidate -> 404
        r = await c.post(
            "/api/v1/resume/analyze",
            headers=h,
            json={"resume_text": RESUME, "candidate_id": "does-not-exist"},
        )
        assert r.status_code == 404, r.text

        # 5) empty resume_text rejected by validation
        r = await c.post(
            "/api/v1/resume/analyze", headers=h, json={"resume_text": ""}
        )
        assert r.status_code == 422, r.text


def test_resume_analyzer_flow():
    asyncio.run(_run_flow())
