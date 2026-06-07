"""Candidate Intelligence Report endpoints (Subsystem 5).

POST /api/v1/reports/interviews/{interview_id}/generate -> build & persist report
GET  /api/v1/reports/interviews/{interview_id}          -> fetch latest report

Tenant isolation + interviewer/super_admin role gating, async SQLAlchemy.
Reuses the existing Report model (content JSON); adds no tables.
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
    Report,
    Scorecard,
    Session,
    TranscriptSegment,
    UserRole,
)
from app.services.llm import get_llm
from app.services.report import generate_report

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

InterviewerDep = require_role(UserRole.interviewer, UserRole.super_admin)


class ReportOut(BaseModel):
    id: str
    interview_id: str
    executive_summary: str
    strengths: list[str]
    weaknesses: list[str]
    risk_indicators: list[str]
    recommended_position: str
    interview_highlights: list[str]
    notable_quotes: list[str]
    role_match_percent: int

    @classmethod
    def from_model(cls, report: Report) -> "ReportOut":
        c = report.content or {}
        return cls(
            id=report.id,
            interview_id=report.interview_id,
            executive_summary=c.get("executive_summary", ""),
            strengths=c.get("strengths", []),
            weaknesses=c.get("weaknesses", []),
            risk_indicators=c.get("risk_indicators", []),
            recommended_position=c.get("recommended_position", "consider"),
            interview_highlights=c.get("interview_highlights", []),
            notable_quotes=c.get("notable_quotes", []),
            role_match_percent=int(c.get("role_match_percent", 0)),
        )


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


@router.post("/interviews/{interview_id}/generate", response_model=ReportOut)
async def generate(
    interview_id: str,
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    iv = await _owned_interview(interview_id, user, db)

    # Sessions belonging to this interview anchor transcript + evaluations.
    session_ids = list(
        await db.scalars(select(Session.id).where(Session.interview_id == iv.id))
    )

    transcript: list[dict] = []
    evaluations: list[dict] = []
    if session_ids:
        segs = await db.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.session_id.in_(session_ids))
            .order_by(TranscriptSegment.start_ms)
        )
        transcript = [
            {"speaker": s.speaker, "text": s.text, "start_ms": s.start_ms}
            for s in segs
        ]
        evals = await db.scalars(
            select(Evaluation).where(Evaluation.session_id.in_(session_ids))
        )
        evaluations = [
            {
                "competency": e.competency,
                "score": e.score,
                "rationale": e.rationale,
            }
            for e in evals
        ]

    sc = await db.scalar(select(Scorecard).where(Scorecard.interview_id == iv.id))
    scorecard = (
        {
            "overall_score": sc.overall_score,
            "competency_scores": sc.competency_scores,
            "recommendation": sc.recommendation,
        }
        if sc
        else None
    )

    content = await generate_report(
        get_llm(),
        interview_title=iv.title,
        job_description=iv.job_description,
        transcript=transcript,
        evaluations=evaluations,
        scorecard=scorecard,
    )

    # Upsert: reuse an existing report row for this interview if present.
    report = await db.scalar(select(Report).where(Report.interview_id == iv.id))
    if report:
        report.content = content
    else:
        report = Report(interview_id=iv.id, content=content)
        db.add(report)
    await db.commit()
    await db.refresh(report)
    return ReportOut.from_model(report)


@router.get("/interviews/{interview_id}", response_model=ReportOut)
async def get_report(
    interview_id: str,
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    iv = await _owned_interview(interview_id, user, db)
    report = await db.scalar(select(Report).where(Report.interview_id == iv.id))
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return ReportOut.from_model(report)
