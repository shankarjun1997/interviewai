"""Candidate Ranking Engine tests.

Runs fully offline (sqlite + stub LLM). Seeds 3 scorecards and asserts the
deterministic ordering for overall + per-dimension rankings, plus that the
narrative recommendation falls back to the deterministic stub.
"""
import asyncio
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_ranking.db")


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


def _app():
    """Build a minimal app that mounts auth + the ranking router under test."""
    from fastapi import FastAPI

    from app.api import auth, ranking

    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(ranking.router)
    return app


def _client(app):
    from httpx import ASGITransport, AsyncClient

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_scorecards(org_id: str):
    """Create a position, 3 candidates+interviews and 3 scorecards."""
    import app.models as m
    from app.db.base import SessionLocal

    async with SessionLocal() as db:
        pos = m.Position(organization_id=org_id, title="Backend Engineer")
        db.add(pos)
        await db.flush()

        # (name, overall, technical, communication, problem_solving, leadership)
        data = [
            ("Alice", 90.0, 95.0, 60.0, 80.0, 50.0),
            ("Bob", 70.0, 50.0, 90.0, 70.0, 95.0),
            ("Carol", 80.0, 70.0, 75.0, 92.0, 60.0),
        ]
        iv_ids = []
        for name, overall, tech, comm, ps, lead in data:
            cand = m.Candidate(organization_id=org_id, full_name=name, email=f"{name.lower()}@x.com")
            db.add(cand)
            await db.flush()
            iv = m.Interview(
                organization_id=org_id,
                position_id=pos.id,
                candidate_id=cand.id,
                created_by="seed",
                title=f"{name} interview",
            )
            db.add(iv)
            await db.flush()
            db.add(
                m.Scorecard(
                    interview_id=iv.id,
                    candidate_id=cand.id,
                    overall_score=overall,
                    competency_scores={
                        "technical": tech,
                        "communication": comm,
                        # mixed shape: dict with score to exercise extractor
                        "problem_solving": {"score": ps, "rationale": "ok"},
                        "leadership": lead,
                    },
                    recommendation="consider",
                )
            )
            iv_ids.append(iv.id)
        await db.commit()
        return pos.id, iv_ids


async def _run():
    import app.models  # noqa: F401  (register tables on Base.metadata)
    from app.db.base import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    app = _app()
    async with _client(app) as c:
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
        org_id = r.json()["organization_id"]
        h = {"Authorization": f"Bearer {token}"}

        pos_id, iv_ids = await _seed_scorecards(org_id)

        # --- compare by position_id ---
        r = await c.post("/api/v1/ranking/compare", headers=h, json={"position_id": pos_id})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] == 3

        overall_names = [e["candidate_name"] for e in body["overall"]]
        assert overall_names == ["Alice", "Carol", "Bob"], overall_names
        assert [e["rank"] for e in body["overall"]] == [1, 2, 3]

        dims = body["dimensions"]
        assert set(dims) == {"technical", "communication", "problem_solving", "leadership"}
        assert [e["candidate_name"] for e in dims["technical"]] == ["Alice", "Carol", "Bob"]
        assert [e["candidate_name"] for e in dims["communication"]] == ["Bob", "Carol", "Alice"]
        assert [e["candidate_name"] for e in dims["problem_solving"]] == ["Carol", "Alice", "Bob"]
        assert [e["candidate_name"] for e in dims["leadership"]] == ["Bob", "Carol", "Alice"]

        # deterministic stub recommendation names the top candidate
        assert "Alice" in body["recommendation"]

        # --- compare by interview_ids ---
        r = await c.post(
            "/api/v1/ranking/compare", headers=h, json={"interview_ids": iv_ids[:2]}
        )
        assert r.status_code == 200, r.text
        assert r.json()["count"] == 2

        # --- validation: must supply a selector ---
        r = await c.post("/api/v1/ranking/compare", headers=h, json={})
        assert r.status_code == 422, r.text

        # --- empty result -> 404 ---
        r = await c.post(
            "/api/v1/ranking/compare", headers=h, json={"position_id": "nonexistent"}
        )
        assert r.status_code == 404, r.text

        # --- auth required ---
        r = await c.post("/api/v1/ranking/compare", json={"position_id": pos_id})
        assert r.status_code == 401, r.text


def test_ranking_engine():
    asyncio.run(_run())
