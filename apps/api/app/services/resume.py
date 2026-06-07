"""AI Resume Analyzer service.

Extracts structured signals from a candidate's resume (skills, experience,
projects, certifications) and, when a job description is supplied, produces an
interview plan: risk areas, missing skills, and suggested questions.

Uses the provider-abstracted LLM client. On the offline StubClient it returns a
deterministic, well-formed result derived from lightweight heuristics so the
flow runs end-to-end without API keys.

Follow-up: plain-text resume only for now. PDF/DOCX parsing is out of scope and
should be added upstream (extract text, then call analyze_resume()).
"""
from __future__ import annotations

import re

from app.services.llm import LLMClient, StubClient

SYSTEM = (
    "You are an expert technical recruiter and interviewer. Analyze the candidate "
    "resume (and job description if provided) and return a structured assessment. "
    "Extract concrete signals only; do not invent experience the resume does not "
    "support. When a job description is provided, identify gaps relative to it."
)

# A compact, curated skill lexicon used by the offline heuristic extractor. It
# is intentionally small and case-insensitive; the LLM path is far richer.
_SKILL_LEXICON = [
    "python", "java", "javascript", "typescript", "go", "golang", "rust", "c++",
    "c#", "ruby", "php", "scala", "kotlin", "swift", "sql", "nosql",
    "react", "angular", "vue", "node", "node.js", "django", "flask", "fastapi",
    "spring", "express", "rails",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "kafka", "rabbitmq", "snowflake", "bigquery",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
    "spark", "hadoop", "airflow", "dbt", "pandas", "numpy",
    "tensorflow", "pytorch", "scikit-learn", "machine learning", "nlp",
    "graphql", "rest", "grpc", "ci/cd", "git", "linux",
]

_CERT_PATTERN = re.compile(
    r"(certified|certification|certificate|aws certified|pmp|cissp|ckad|cka|"
    r"scrum master|professional cloud|azure (?:fundamentals|administrator))",
    re.IGNORECASE,
)

_YEARS_PATTERN = re.compile(r"(\d{1,2})\+?\s*(?:years|yrs)", re.IGNORECASE)


async def analyze_resume(
    llm: LLMClient,
    *,
    resume_text: str,
    job_description: str = "",
) -> dict:
    """Return a structured analysis dict. Always well-formed, never raises on
    LLM/parse failure (falls back to the heuristic analyzer)."""
    if isinstance(llm, StubClient):
        return _heuristic_analysis(resume_text, job_description)

    prompt = (
        f"Resume:\n{resume_text or '(empty)'}\n\n"
        f"Job description:\n{job_description or '(not provided)'}\n\n"
        "Return JSON with exactly these keys:\n"
        '{"skills": [str], "experience": [{"title", "company", "summary", '
        '"years"}], "projects": [{"name", "description"}], '
        '"certifications": [str], "missing_skills": [str], "risk_areas": [str], '
        '"interview_plan": [{"round", "focus", "rationale"}], '
        '"suggested_questions": [{"type", "text", "competencies": [str]}]}'
    )
    try:
        data = await llm.complete_json(system=SYSTEM, prompt=prompt)
        if isinstance(data, dict) and data.get("skills") is not None:
            return _normalize(data)
    except Exception:
        pass
    return _heuristic_analysis(resume_text, job_description)


def _normalize(data: dict) -> dict:
    """Coerce an LLM result into the canonical shape with all keys present."""
    return {
        "skills": list(data.get("skills") or []),
        "experience": list(data.get("experience") or []),
        "projects": list(data.get("projects") or []),
        "certifications": list(data.get("certifications") or []),
        "missing_skills": list(data.get("missing_skills") or []),
        "risk_areas": list(data.get("risk_areas") or []),
        "interview_plan": list(data.get("interview_plan") or []),
        "suggested_questions": list(data.get("suggested_questions") or []),
        "source": "llm",
    }


def _heuristic_analysis(resume_text: str, job_description: str) -> dict:
    text = resume_text or ""
    lower = text.lower()

    skills = _extract_skills(lower)
    jd_skills = _extract_skills(job_description.lower()) if job_description else []
    missing = [s for s in jd_skills if s not in skills]

    years = _max_years(text)
    certifications = _extract_certifications(text)
    experience = _extract_experience(text, years)
    projects = _extract_projects(text)

    risk_areas: list[str] = []
    if not skills:
        risk_areas.append("No recognizable technical skills found in resume text.")
    if missing:
        risk_areas.append(
            "Missing job-required skills: " + ", ".join(missing) + "."
        )
    if years is not None and years < 2:
        risk_areas.append("Limited overall experience (<2 years).")
    if not certifications:
        risk_areas.append("No certifications detected.")

    interview_plan = _build_plan(skills, missing)
    suggested_questions = _build_questions(skills, missing)

    return {
        "skills": skills,
        "experience": experience,
        "projects": projects,
        "certifications": certifications,
        "missing_skills": missing,
        "risk_areas": risk_areas,
        "interview_plan": interview_plan,
        "suggested_questions": suggested_questions,
        "source": "stub",
    }


def _extract_skills(text: str) -> list[str]:
    found: list[str] = []
    for skill in _SKILL_LEXICON:
        # word-ish boundary match; escape regex metacharacters in the term
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, text):
            if skill not in found:
                found.append(skill)
    return found


def _max_years(text: str) -> int | None:
    matches = [int(m) for m in _YEARS_PATTERN.findall(text)]
    return max(matches) if matches else None


def _extract_certifications(text: str) -> list[str]:
    certs: list[str] = []
    for line in text.splitlines():
        if _CERT_PATTERN.search(line):
            cleaned = line.strip(" -*\t")
            if cleaned and cleaned not in certs:
                certs.append(cleaned)
    return certs


def _extract_experience(text: str, years: int | None) -> list[dict]:
    """Heuristic: surface lines that look like role headers (contain 'at' or a
    title keyword). Kept conservative to avoid hallucinated structure."""
    title_kw = ("engineer", "developer", "manager", "lead", "architect",
                "analyst", "scientist", "intern", "consultant", "director")
    exp: list[dict] = []
    for line in text.splitlines():
        ln = line.strip()
        low = ln.lower()
        if not ln or len(ln) > 160:
            continue
        if any(k in low for k in title_kw):
            company = ""
            if " at " in low:
                company = ln.split(" at ", 1)[1].strip()
            exp.append(
                {
                    "title": ln,
                    "company": company,
                    "summary": "",
                    "years": years,
                }
            )
        if len(exp) >= 10:
            break
    return exp


def _extract_projects(text: str) -> list[dict]:
    projects: list[dict] = []
    in_section = False
    for line in text.splitlines():
        ln = line.strip()
        low = ln.lower()
        if low.startswith("project"):
            in_section = True
            continue
        if in_section and ln:
            if low.startswith(("experience", "education", "skills", "certification")):
                in_section = False
                continue
            projects.append({"name": ln[:80], "description": ""})
        if len(projects) >= 10:
            break
    return projects


def _build_plan(skills: list[str], missing: list[str]) -> list[dict]:
    plan = [
        {
            "round": "Introduction",
            "focus": "Background and motivation",
            "rationale": "Establish rapport and verify the resume narrative.",
        },
        {
            "round": "Technical deep-dive",
            "focus": ", ".join(skills[:5]) or "general fundamentals",
            "rationale": "Probe the strongest claimed skills for depth.",
        },
    ]
    if missing:
        plan.append(
            {
                "round": "Gap assessment",
                "focus": ", ".join(missing[:5]),
                "rationale": "Evaluate ability to ramp on job-required skills not on the resume.",
            }
        )
    plan.append(
        {
            "round": "Behavioral",
            "focus": "Collaboration and problem solving",
            "rationale": "Assess communication and culture fit.",
        }
    )
    return plan


def _build_questions(skills: list[str], missing: list[str]) -> list[dict]:
    questions: list[dict] = [
        {
            "type": "intro",
            "text": "Walk me through your background and the work you're most proud of.",
            "competencies": ["communication"],
        }
    ]
    for skill in skills[:3]:
        questions.append(
            {
                "type": "technical",
                "text": f"Describe a challenging problem you solved using {skill}.",
                "competencies": ["technical", "problem_solving"],
            }
        )
    for skill in missing[:2]:
        questions.append(
            {
                "type": "technical",
                "text": (
                    f"This role uses {skill}, which I don't see on your resume. "
                    f"How would you approach getting up to speed on it?"
                ),
                "competencies": ["technical", "problem_solving"],
            }
        )
    questions.append(
        {
            "type": "behavioral",
            "text": "Tell me about a time you disagreed with a teammate and how you resolved it.",
            "competencies": ["communication", "culture_fit"],
        }
    )
    return questions
