"""End-to-end smoke test of the walking skeleton: register -> create interview
-> generate questions. Runs fully offline (sqlite + stub LLM)."""
import asyncio
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_smoke.db")


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


def _client():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _run_flow():
    import app.models  # noqa: F401  (register tables on Base.metadata)
    from app.db.base import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _client() as c:
        r = await c.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Acme",
                "email": "lead@acme.com",
                "password": "supersecret",
                "full_name": "Lead",
            },
        )
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        r = await c.post(
            "/api/v1/interviews",
            headers=h,
            json={"title": "Senior Data Engineer", "job_description": "Spark, dbt, GCP", "difficulty": "hard"},
        )
        assert r.status_code == 201, r.text
        iv_id = r.json()["id"]

        r = await c.post(
            f"/api/v1/interviews/{iv_id}/generate-questions",
            headers=h,
            json={"counts": {"intro": 1, "behavioral": 2, "technical": 3}},
        )
        assert r.status_code == 200, r.text
        questions = r.json()
        assert len(questions) == 6, questions

        # tenant isolation: a request with no token is rejected
        r = await c.get("/api/v1/interviews")
        assert r.status_code == 401


def test_walking_skeleton():
    asyncio.run(_run_flow())
