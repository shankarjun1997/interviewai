from pydantic import BaseModel, EmailStr, Field


# ---- auth ----
class RegisterRequest(BaseModel):
    organization_name: str
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    organization_id: str


# ---- interviews ----
class InterviewCreate(BaseModel):
    title: str
    job_description: str = ""
    position_id: str | None = None
    difficulty: str = "medium"


class QuestionOut(BaseModel):
    id: str
    type: str
    text: str
    difficulty: str
    competencies: list[str] = []
    order_index: int = 0

    class Config:
        from_attributes = True


class InterviewOut(BaseModel):
    id: str
    title: str
    job_description: str
    difficulty: str
    status: str

    class Config:
        from_attributes = True


class GenerateQuestionsRequest(BaseModel):
    counts: dict[str, int] = {"technical": 5, "behavioral": 3, "intro": 2}
