"""Scoring Framework router.

Computes a role-weighted Scorecard for an interview from its per-competency
Evaluation rows and the Position's scoring_weights. Reuses existing models;
creates no new tables.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.base import get_db
from app.models import (
    Evaluation,
    Interview,
    Position,
    Scorecard,
    Session,
    UserRole,
)
from app.services.scoring import compute_score

router = APIRouter(prefix="/api/v1/scoring", tags=["scoring"])

InterviewerDep = require_role(UserRole.interviewer, UserRole.super_admin)


class ScorecardOut(BaseModel):
    id: str
    interview_id: str
    candidate_id: str | None = None
    overall_score: float
    competency_scores: dict
    recommendation: str

    model_config = {"from_attributes": True}


async def _owned_interview(
    interview_id: str, user: CurrentUser, db: AsyncSession
) -> Interview:
    iv = await db.scalar(
        select(Interview).where(
            Interview.id == interview_id,
            Interview.organization_id == user.organization_id,  # tenant isolation
        )
    )
    if not iv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return iv


async def _gather_evaluations(
    interview_id: str, db: AsyncSession
) -> list[tuple[str, float]]:
    rows = await db.scalars(
        select(Evaluation)
        .join(Session, Session.id == Evaluation.session_id)
        .where(Session.interview_id == interview_id)
    )
    return [(e.competency, e.score) for e in rows]


@router.post(
    "/interviews/{interview_id}/compute",
    response_model=ScorecardOut,
)
async def compute_scorecard(
    interview_id: str,
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    iv = await _owned_interview(interview_id, user, db)

    evaluations = await _gather_evaluations(iv.id, db)
    if not evaluations:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No evaluations found for this interview",
        )

    weights: dict | None = None
    is_technical = True
    if iv.position_id:
        position = await db.scalar(
            select(Position).where(
                Position.id == iv.position_id,
                Position.organization_id == user.organization_id,
            )
        )
        if position:
            weights = position.scoring_weights or None
            is_technical = position.is_technical

    result = compute_score(evaluations, weights, is_technical=is_technical)

    scorecard = await db.scalar(
        select(Scorecard).where(Scorecard.interview_id == iv.id)
    )
    if scorecard is None:
        scorecard = Scorecard(interview_id=iv.id, candidate_id=iv.candidate_id)
        db.add(scorecard)

    scorecard.candidate_id = iv.candidate_id
    scorecard.overall_score = result.overall_score
    scorecard.competency_scores = result.competency_scores
    scorecard.recommendation = result.recommendation.value

    await db.commit()
    await db.refresh(scorecard)
    return scorecard


@router.get(
    "/interviews/{interview_id}/scorecard",
    response_model=ScorecardOut,
)
async def get_scorecard(
    interview_id: str,
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    iv = await _owned_interview(interview_id, user, db)
    scorecard = await db.scalar(
        select(Scorecard).where(Scorecard.interview_id == iv.id)
    )
    if scorecard is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Scorecard not computed yet",
        )
    return scorecard
