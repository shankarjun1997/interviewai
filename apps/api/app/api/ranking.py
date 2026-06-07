"""Candidate Ranking Engine API.

POST /api/v1/ranking/compare — rank candidates' scorecards either across a
whole position (position_id) or for an explicit list of interview_ids. Returns
a deterministic overall ranking + per-dimension rankings, plus an AI narrative
recommendation (deterministic stub offline). Tenant-isolated; interviewer /
super_admin only.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.base import get_db
from app.models import Candidate, Interview, Scorecard, UserRole
from app.services.llm import get_llm
from app.services.ranking import (
    DIMENSIONS,
    CandidateScores,
    generate_recommendation,
    rank_candidates,
)

router = APIRouter(prefix="/api/v1/ranking", tags=["ranking"])

InterviewerDep = require_role(UserRole.interviewer, UserRole.super_admin)


# ----- local Pydantic schemas -----
class CompareRequest(BaseModel):
    position_id: str | None = None
    interview_ids: list[str] | None = None

    @model_validator(mode="after")
    def _one_selector(self) -> "CompareRequest":
        if not self.position_id and not self.interview_ids:
            raise ValueError("Provide either position_id or interview_ids")
        if self.position_id and self.interview_ids:
            raise ValueError("Provide only one of position_id or interview_ids")
        return self


class RankedEntryOut(BaseModel):
    rank: int
    interview_id: str
    scorecard_id: str
    candidate_id: str | None = None
    candidate_name: str
    score: float


class CompareResponse(BaseModel):
    count: int
    overall: list[RankedEntryOut]
    dimensions: dict[str, list[RankedEntryOut]]
    recommendation: str
    dimension_names: list[str] = Field(default_factory=lambda: list(DIMENSIONS))


async def _load_candidate_scores(
    body: CompareRequest, user: CurrentUser, db: AsyncSession
) -> list[CandidateScores]:
    # Join scorecards to interviews so we can enforce tenant isolation via the
    # interview's organization_id (Scorecard has no org column).
    stmt = (
        select(Scorecard, Interview, Candidate)
        .join(Interview, Scorecard.interview_id == Interview.id)
        .outerjoin(Candidate, Scorecard.candidate_id == Candidate.id)
        .where(Interview.organization_id == user.organization_id)
    )
    if body.position_id:
        stmt = stmt.where(Interview.position_id == body.position_id)
    else:
        stmt = stmt.where(Scorecard.interview_id.in_(body.interview_ids))

    rows = (await db.execute(stmt)).all()
    out: list[CandidateScores] = []
    for sc, iv, cand in rows:
        name = (cand.full_name if cand else None) or iv.title or sc.interview_id
        out.append(
            CandidateScores(
                interview_id=sc.interview_id,
                scorecard_id=sc.id,
                candidate_id=sc.candidate_id,
                candidate_name=name,
                overall_score=float(sc.overall_score or 0.0),
                competency_scores=sc.competency_scores or {},
                recommendation=sc.recommendation or "",
            )
        )
    return out


@router.post("/compare", response_model=CompareResponse)
async def compare(
    body: CompareRequest,
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    candidates = await _load_candidate_scores(body, user, db)
    if not candidates:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No scorecards found for the given selector"
        )

    overall, dimensions = rank_candidates(candidates)
    recommendation = await generate_recommendation(get_llm(), overall, dimensions)

    return CompareResponse(
        count=len(candidates),
        overall=[RankedEntryOut(**e.__dict__) for e in overall],
        dimensions={
            dim: [RankedEntryOut(**e.__dict__) for e in entries]
            for dim, entries in dimensions.items()
        },
        recommendation=recommendation,
    )
