"""AI Question Engine (Cycle 1, core to the walking skeleton).

Generates role/JD-aware interview questions. Uses the LLM abstraction; falls back
to a sensible template bank when running on the stub client.
"""
from __future__ import annotations

from app.services.llm import LLMClient, StubClient

SYSTEM = (
    "You are an expert technical interviewer. Generate high-signal interview "
    "questions tailored to the job description and difficulty. For each question "
    "return: type, text, difficulty, ideal_answer (1-3 sentences), competencies "
    "(list of: technical, communication, problem_solving, leadership, culture_fit)."
)

_FALLBACK = {
    "intro": [
        "Walk me through your background and what drew you to this role.",
        "What are you looking for in your next position?",
    ],
    "behavioral": [
        "Tell me about a time you disagreed with a teammate. How did you resolve it?",
        "Describe a project that failed. What did you learn?",
        "Give an example of when you had to learn something quickly under pressure.",
    ],
    "technical": [
        "Explain a system you designed end to end and the key trade-offs.",
        "How would you debug a production service that's intermittently slow?",
        "What does idempotency mean and where have you relied on it?",
        "How do you decide between SQL and NoSQL for a new feature?",
        "Describe how you ensure data quality in a pipeline.",
    ],
}


async def generate_questions(
    llm: LLMClient,
    *,
    job_description: str,
    difficulty: str,
    counts: dict[str, int],
) -> list[dict]:
    if isinstance(llm, StubClient):
        return _from_fallback(counts, difficulty)

    prompt = (
        f"Job description:\n{job_description or '(not provided)'}\n\n"
        f"Difficulty: {difficulty}\n"
        f"Generate exactly these counts by type: {counts}.\n"
        'Return JSON: {"questions": [{"type","text","difficulty","ideal_answer","competencies"}]}'
    )
    try:
        data = await llm.complete_json(system=SYSTEM, prompt=prompt)
        questions = data.get("questions", [])
        if questions:
            return questions
    except Exception:
        pass
    return _from_fallback(counts, difficulty)


def _from_fallback(counts: dict[str, int], difficulty: str) -> list[dict]:
    out: list[dict] = []
    for qtype, n in counts.items():
        bank = _FALLBACK.get(qtype, _FALLBACK["technical"])
        for i in range(n):
            out.append(
                {
                    "type": qtype if qtype in _FALLBACK else "technical",
                    "text": bank[i % len(bank)],
                    "difficulty": difficulty,
                    "ideal_answer": "",
                    "competencies": ["technical"] if qtype == "technical" else ["communication"],
                }
            )
    return out
