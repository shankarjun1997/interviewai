import enum

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    interviewer = "interviewer"
    candidate = "candidate"


class InterviewStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class QuestionType(str, enum.Enum):
    intro = "intro"
    behavioral = "behavioral"
    technical = "technical"
    scenario = "scenario"
    architecture = "architecture"
    leadership = "leadership"
    rapid_fire = "rapid_fire"
    coding = "coding"
    custom = "custom"


class Organization(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(50), default="free")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    users: Mapped[list["User"]] = relationship(back_populates="organization")


class User(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "users"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.interviewer)

    organization: Mapped[Organization] = relationship(back_populates="users")


class Position(Base, UUIDPKMixin, TimestampMixin):
    """A role being hired for; carries its competency weighting profile."""
    __tablename__ = "positions"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    is_technical: Mapped[bool] = mapped_column(default=True)
    # competency -> weight (0..1), e.g. {"technical": 0.6, "communication": 0.1, ...}
    scoring_weights: Mapped[dict] = mapped_column(JSON, default=dict)


class Candidate(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "candidates"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320), index=True)
    resume_text: Mapped[str] = mapped_column(Text, default="")


class Interview(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "interviews"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    position_id: Mapped[str | None] = mapped_column(ForeignKey("positions.id"), nullable=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255))
    job_description: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[InterviewStatus] = mapped_column(String(20), default=InterviewStatus.draft)

    rounds: Mapped[list["InterviewRound"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )


class InterviewRound(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "interview_rounds"
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    interview: Mapped[Interview] = relationship(back_populates="rounds")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="round", cascade="all, delete-orphan"
    )


class Question(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "questions"
    round_id: Mapped[str] = mapped_column(ForeignKey("interview_rounds.id"), index=True)
    type: Mapped[QuestionType] = mapped_column(String(20), default=QuestionType.technical)
    text: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    ideal_answer: Mapped[str] = mapped_column(Text, default="")
    competencies: Mapped[list] = mapped_column(JSON, default=list)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    round: Mapped[InterviewRound] = relationship(back_populates="questions")


class Session(Base, UUIDPKMixin, TimestampMixin):
    """A live run of a round."""
    __tablename__ = "sessions"
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), index=True)
    round_id: Mapped[str | None] = mapped_column(ForeignKey("interview_rounds.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="created")


class TranscriptSegment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "transcript_segments"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    speaker: Mapped[str] = mapped_column(String(50), default="candidate")
    text: Mapped[str] = mapped_column(Text)
    start_ms: Mapped[int] = mapped_column(Integer, default=0)
    end_ms: Mapped[int] = mapped_column(Integer, default=0)


class Evaluation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "evaluations"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    competency: Mapped[str] = mapped_column(String(50))
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100
    rationale: Mapped[str] = mapped_column(Text, default="")


class Scorecard(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "scorecards"
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), index=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    competency_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    recommendation: Mapped[str] = mapped_column(String(20), default="consider")


class Report(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "reports"
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), index=True)
    content: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditLog(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "audit_logs"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(255), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
