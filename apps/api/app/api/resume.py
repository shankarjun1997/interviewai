"""AI Resume Analyzer endpoint.

POST /api/v1/resume/analyze
  Accepts plain-text resume (and optional job description). Extracts structured
  signals and produces an interview plan. If candidate_id is supplied, the
  resume_text is persisted on that (tenant-scoped) Candidate; otherwise the
  text is analyzed ad-hoc and nothing is stored.

Schemas are defined locally (not in app/schemas) to keep this subsystem
self-contained.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.base import get_db
from app.models import Candidate, UserRole
from app.services.llm import get_llm
from app.services.resume import analyze_resume

router = APIRouter(prefix="/api/v1/resume", tags=["resume"])

InterviewerDep = require_role(UserRole.interviewer, UserRole.super_admin)


# ---- local schemas ----
class AnalyzeResumeRequest(BaseModel):
    resume_text: str = Field(min_length=1)
    job_description: str = ""
    candidate_id: str | None = None


class ExperienceItem(BaseModel):
    title: str = ""
    company: str = ""
    summary: str = ""
    years: int | None = None


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""


class PlanItem(BaseModel):
    round: str = ""
    focus: str = ""
    rationale: str = ""


class SuggestedQuestion(BaseModel):
    type: str = "technical"
    text: str = ""
    competencies: list[str] = []


class AnalyzeResumeResponse(BaseModel):
    candidate_id: str | None = None
    persisted: bool = False
    skills: list[str] = []
    experience: list[ExperienceItem] = []
    projects: list[ProjectItem] = []
    certifications: list[str] = []
    missing_skills: list[str] = []
    risk_areas: list[str] = []
    interview_plan: list[PlanItem] = []
    suggested_questions: list[SuggestedQuestion] = []
    source: str = "stub"


@router.post("/analyze", response_model=AnalyzeResumeResponse)
async def analyze(
    body: AnalyzeResumeRequest,
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    persisted = False
    candidate_id: str | None = None

    if body.candidate_id is not None:
        candidate = await db.scalar(
            select(Candidate).where(
                Candidate.id == body.candidate_id,
                Candidate.organization_id == user.organization_id,  # tenant isolation
            )
        )
        if not candidate:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
        candidate.resume_text = body.resume_text
        await db.commit()
        persisted = True
        candidate_id = candidate.id

    analysis = await analyze_resume(
        get_llm(),
        resume_text=body.resume_text,
        job_description=body.job_description,
    )

    return AnalyzeResumeResponse(
        candidate_id=candidate_id,
        persisted=persisted,
        **analysis,
    )
