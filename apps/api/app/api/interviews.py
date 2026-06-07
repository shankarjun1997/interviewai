from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.base import get_db
from app.models import (
    Interview,
    InterviewRound,
    Question,
    QuestionType,
    UserRole,
)
from app.schemas import (
    GenerateQuestionsRequest,
    InterviewCreate,
    InterviewOut,
    QuestionOut,
)
from app.services.llm import get_llm
from app.services.question_engine import generate_questions

router = APIRouter(prefix="/api/v1/interviews", tags=["interviews"])

InterviewerDep = require_role(UserRole.interviewer, UserRole.super_admin)


async def _owned_interview(interview_id: str, user: CurrentUser, db: AsyncSession) -> Interview:
    iv = await db.scalar(
        select(Interview).where(
            Interview.id == interview_id,
            Interview.organization_id == user.organization_id,  # tenant isolation
        )
    )
    if not iv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return iv


@router.post("", response_model=InterviewOut, status_code=201)
async def create_interview(
    body: InterviewCreate,
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    iv = Interview(
        organization_id=user.organization_id,
        created_by=user.id,
        title=body.title,
        job_description=body.job_description,
        position_id=body.position_id,
        difficulty=body.difficulty,
    )
    db.add(iv)
    await db.flush()
    db.add(InterviewRound(interview_id=iv.id, name="Round 1", order_index=0))
    await db.commit()
    return iv


@router.get("", response_model=list[InterviewOut])
async def list_interviews(
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(Interview).where(Interview.organization_id == user.organization_id)
    )
    return list(rows)


@router.post("/{interview_id}/generate-questions", response_model=list[QuestionOut])
async def generate(
    interview_id: str,
    body: GenerateQuestionsRequest,
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    iv = await _owned_interview(interview_id, user, db)
    round_ = await db.scalar(
        select(InterviewRound)
        .where(InterviewRound.interview_id == iv.id)
        .order_by(InterviewRound.order_index)
    )
    if not round_:
        round_ = InterviewRound(interview_id=iv.id, name="Round 1")
        db.add(round_)
        await db.flush()

    generated = await generate_questions(
        get_llm(),
        job_description=iv.job_description,
        difficulty=iv.difficulty,
        counts=body.counts,
    )
    created: list[Question] = []
    for idx, q in enumerate(generated):
        qtype = q.get("type", "technical")
        try:
            qtype_enum = QuestionType(qtype)
        except ValueError:
            qtype_enum = QuestionType.technical
        question = Question(
            round_id=round_.id,
            type=qtype_enum,
            text=q["text"],
            difficulty=q.get("difficulty", iv.difficulty),
            ideal_answer=q.get("ideal_answer", ""),
            competencies=q.get("competencies", []),
            order_index=idx,
        )
        db.add(question)
        created.append(question)
    await db.commit()
    return created
