"""Tests for the Scoring Framework subsystem.

Runs fully offline against a fresh sqlite DB. Covers the pure scoring math and
the two HTTP endpoints (compute + fetch) including tenant isolation and auth.
"""
import asyncio
import os

import pytest

# Fresh DB before any app module imports the engine.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_scoring.db"

if os.path.exists("./test_scoring.db"):
    os.remove("./test_scoring.db")


# --------------------------------------------------------------------------- #
# Pure scoring-logic tests (no DB)
# --------------------------------------------------------------------------- #
def test_data_engineer_example_from_spec():
    from app.services.scoring import (
        DATA_ENGINEER_WEIGHTS,
        Recommendation,
        compute_score,
    )

    evals = [
        ("technical", 90.0),
        ("communication", 70.0),
        ("problem_solving", 80.0),
        ("leadership", 60.0),
        ("culture_fit", 60.0),
    ]
    result = compute_score(evals, DATA_ENGINEER_WEIGHTS, is_technical=True)
    # 90*.6 + 70*.1 + 80*.2 + 60*.05 + 60*.05 = 54 + 7 + 16 + 3 + 3 = 83
    assert result.overall_score == pytest.approx(83.0)
    assert result.recommendation == Recommendation.hire
    assert result.competency_scores["technical"]["weight"] == pytest.approx(0.6)
    assert result.competency_scores["technical"]["contribution"] == pytest.approx(54.0)


def test_averages_multiple_evals_per_competency():
    from app.services.scoring import compute_score

    evals = [("technical", 100.0), ("technical", 80.0), ("communication", 50.0)]
    result = compute_score(evals, {"technical": 0.5, "communication": 0.5})
    assert result.competency_scores["technical"]["score"] == pytest.approx(90.0)
    # 90*.5 + 50*.5 = 70
    assert result.overall_score == pytest.approx(70.0)


def test_recommendation_thresholds():
    from app.services.scoring import Recommendation, recommend

    assert recommend(95) == Recommendation.strong_hire
    assert recommend(85) == Recommendation.strong_hire
    assert recommend(75) == Recommendation.hire
    assert recommend(60) == Recommendation.consider
    assert recommend(45) == Recommendation.weak_hire
    assert recommend(10) == Recommendation.reject


def test_weights_renormalized_over_evaluated_competencies():
    from app.services.scoring import compute_score

    # Only "technical" was evaluated though profile spans many competencies.
    evals = [("technical", 80.0)]
    result = compute_score(evals, {"technical": 0.6, "communication": 0.4})
    assert result.competency_scores["technical"]["weight"] == pytest.approx(1.0)
    assert result.overall_score == pytest.approx(80.0)


def test_default_profiles_differ_by_role_type():
    from app.services.scoring import default_weights

    tech = default_weights(True)
    non_tech = default_weights(False)
    assert tech["technical"] > non_tech["technical"]
    assert non_tech["communication"] > tech["communication"]
    assert sum(tech.values()) == pytest.approx(1.0)
    assert sum(non_tech.values()) == pytest.approx(1.0)


def test_no_weight_overlap_falls_back_to_plain_average():
    from app.services.scoring import compute_score

    evals = [("design", 80.0), ("ethics", 40.0)]
    result = compute_score(evals, {"technical": 1.0})
    assert result.overall_score == pytest.approx(60.0)


# --------------------------------------------------------------------------- #
# Endpoint tests (DB + ASGI)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


def _client():
    from httpx import ASGITransport, AsyncClient

    from app.api import scoring as scoring_router
    from app.main import app

    # Wire our router without editing the shared app.main (see report note).
    if not any(r.path.startswith("/api/v1/scoring") for r in app.routes):
        app.include_router(scoring_router.router)

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_tables():
    import app.models  # noqa: F401  (register tables on Base.metadata)
    from app.db.base import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _seed_interview_with_evals(token_org_id, weights, is_technical, scores):
    """Create a Position, Interview, Session, and Evaluation rows directly."""
    from app.db.base import SessionLocal
    from app.models import Evaluation, Interview, Position, Session

    async with SessionLocal() as db:
        position = Position(
            organization_id=token_org_id,
            title="Senior Data Engineer",
            is_technical=is_technical,
            scoring_weights=weights,
        )
        db.add(position)
        await db.flush()

        iv = Interview(
            organization_id=token_org_id,
            position_id=position.id,
            created_by="seed-user",
            title="DE interview",
        )
        db.add(iv)
        await db.flush()

        sess = Session(interview_id=iv.id, status="completed")
        db.add(sess)
        await db.flush()

        for competency, score in scores:
            db.add(
                Evaluation(
                    session_id=sess.id, competency=competency, score=score
                )
            )
        await db.commit()
        return iv.id


async def _register(c, org="Acme", email="lead@acme.com"):
    r = await c.post(
        "/api/v1/auth/register",
        json={
            "organization_name": org,
            "email": email,
            "password": "supersecret",
            "full_name": "Lead",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body["access_token"], body["organization_id"]


async def _run_endpoint_flow():
    await _create_tables()

    async with _client() as c:
        token, org_id = await _register(c)
        h = {"Authorization": f"Bearer {token}"}

        iv_id = await _seed_interview_with_evals(
            org_id,
            weights={
                "technical": 0.6,
                "communication": 0.1,
                "problem_solving": 0.2,
                "leadership": 0.05,
                "culture_fit": 0.05,
            },
            is_technical=True,
            scores=[
                ("technical", 90.0),
                ("communication", 70.0),
                ("problem_solving", 80.0),
                ("leadership", 60.0),
                ("culture_fit", 60.0),
            ],
        )

        # No auth -> 401
        r = await c.post(f"/api/v1/scoring/interviews/{iv_id}/compute")
        assert r.status_code == 401, r.text

        # Scorecard not computed yet -> 404
        r = await c.get(f"/api/v1/scoring/interviews/{iv_id}/scorecard", headers=h)
        assert r.status_code == 404, r.text

        # Compute
        r = await c.post(
            f"/api/v1/scoring/interviews/{iv_id}/compute", headers=h
        )
        assert r.status_code == 200, r.text
        sc = r.json()
        assert sc["overall_score"] == pytest.approx(83.0)
        assert sc["recommendation"] == "hire"
        assert sc["competency_scores"]["technical"]["contribution"] == pytest.approx(54.0)

        # Idempotent recompute updates the same scorecard
        r2 = await c.post(
            f"/api/v1/scoring/interviews/{iv_id}/compute", headers=h
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["id"] == sc["id"]

        # Fetch
        r = await c.get(
            f"/api/v1/scoring/interviews/{iv_id}/scorecard", headers=h
        )
        assert r.status_code == 200, r.text
        assert r.json()["overall_score"] == pytest.approx(83.0)

        # Tenant isolation: another org cannot see this interview
        token2, _ = await _register(c, org="Beta", email="lead@beta.com")
        h2 = {"Authorization": f"Bearer {token2}"}
        r = await c.get(
            f"/api/v1/scoring/interviews/{iv_id}/scorecard", headers=h2
        )
        assert r.status_code == 404, r.text
        r = await c.post(
            f"/api/v1/scoring/interviews/{iv_id}/compute", headers=h2
        )
        assert r.status_code == 404, r.text


async def _run_no_evaluations_flow():
    await _create_tables()
    from app.db.base import SessionLocal
    from app.models import Interview

    async with _client() as c:
        token, org_id = await _register(c, org="Gamma", email="lead@gamma.com")
        h = {"Authorization": f"Bearer {token}"}

        async with SessionLocal() as db:
            iv = Interview(
                organization_id=org_id,
                created_by="seed-user",
                title="Empty interview",
            )
            db.add(iv)
            await db.commit()
            iv_id = iv.id

        r = await c.post(
            f"/api/v1/scoring/interviews/{iv_id}/compute", headers=h
        )
        assert r.status_code == 400, r.text


def test_scoring_endpoints():
    asyncio.run(_run_endpoint_flow())


def test_compute_without_evaluations_returns_400():
    asyncio.run(_run_no_evaluations_flow())
