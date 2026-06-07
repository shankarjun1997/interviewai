"""Candidate Intelligence Report generation (Subsystem 5).

Builds a structured intelligence report from an interview's transcript segments,
per-competency evaluations, and aggregated scorecard. Uses the LLM abstraction;
falls back to a deterministic, well-formed stub report when running on the stub
client so the endpoint works fully offline (no API key).
"""
from __future__ import annotations

from typing import Any

from app.services.llm import LLMClient, StubClient

# Allowed recommendation values for recommended_position.
RECOMMENDATIONS = ("strong_hire", "hire", "consider", "weak_hire", "reject")

SYSTEM = (
    "You are a senior hiring panelist producing a candidate intelligence report. "
    "Analyze the interview transcript, per-competency evaluations and scorecard. "
    "Be specific, evidence-based and concise. Return JSON only with keys: "
    "executive_summary (a single string of exactly 3 paragraphs separated by \\n\\n), "
    "strengths (list of up to 10 strings), weaknesses (list of up to 10 strings), "
    "risk_indicators (list of strings), "
    "recommended_position (one of strong_hire|hire|consider|weak_hire|reject), "
    "interview_highlights (list of strings), "
    "notable_quotes (list of strings, verbatim from the candidate), "
    "role_match_percent (integer 0-100)."
)


def _score_to_recommendation(score: float) -> str:
    if score >= 85:
        return "strong_hire"
    if score >= 70:
        return "hire"
    if score >= 55:
        return "consider"
    if score >= 40:
        return "weak_hire"
    return "reject"


def build_prompt(
    *,
    interview_title: str,
    job_description: str,
    transcript: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    scorecard: dict[str, Any] | None,
) -> str:
    """Assemble a deterministic prompt from interview context."""
    lines: list[str] = []
    lines.append(f"Interview: {interview_title}")
    lines.append(f"Job description:\n{job_description or '(not provided)'}")

    lines.append("\nTranscript:")
    if transcript:
        for seg in transcript:
            speaker = seg.get("speaker", "candidate")
            text = seg.get("text", "")
            lines.append(f"  [{speaker}] {text}")
    else:
        lines.append("  (no transcript captured)")

    lines.append("\nPer-competency evaluations:")
    if evaluations:
        for ev in evaluations:
            lines.append(
                f"  {ev.get('competency', 'general')}: "
                f"{ev.get('score', 0)} - {ev.get('rationale', '')}"
            )
    else:
        lines.append("  (no evaluations recorded)")

    lines.append("\nScorecard:")
    if scorecard:
        lines.append(f"  overall_score: {scorecard.get('overall_score', 0)}")
        lines.append(f"  recommendation: {scorecard.get('recommendation', 'consider')}")
        lines.append(f"  competency_scores: {scorecard.get('competency_scores', {})}")
    else:
        lines.append("  (no scorecard available)")

    lines.append(
        '\nReturn JSON with keys: executive_summary, strengths, weaknesses, '
        "risk_indicators, recommended_position, interview_highlights, "
        "notable_quotes, role_match_percent."
    )
    return "\n".join(lines)


def _normalize(data: dict[str, Any], overall_score: float) -> dict[str, Any]:
    """Coerce an LLM/stub payload into the strict report schema."""

    def _as_list(v: Any, cap: int | None = None) -> list[str]:
        if isinstance(v, list):
            out = [str(x) for x in v if str(x).strip()]
        elif v:
            out = [str(v)]
        else:
            out = []
        return out[:cap] if cap else out

    rec = str(data.get("recommended_position", "")).strip()
    if rec not in RECOMMENDATIONS:
        rec = _score_to_recommendation(overall_score)

    try:
        role_match = int(round(float(data.get("role_match_percent", overall_score))))
    except (TypeError, ValueError):
        role_match = int(round(overall_score))
    role_match = max(0, min(100, role_match))

    summary = data.get("executive_summary", "")
    if isinstance(summary, list):
        summary = "\n\n".join(str(p) for p in summary)
    summary = str(summary).strip()

    return {
        "executive_summary": summary,
        "strengths": _as_list(data.get("strengths"), 10),
        "weaknesses": _as_list(data.get("weaknesses"), 10),
        "risk_indicators": _as_list(data.get("risk_indicators")),
        "recommended_position": rec,
        "interview_highlights": _as_list(data.get("interview_highlights")),
        "notable_quotes": _as_list(data.get("notable_quotes")),
        "role_match_percent": role_match,
    }


def _stub_report(
    *,
    interview_title: str,
    transcript: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    scorecard: dict[str, Any] | None,
) -> dict[str, Any]:
    """Deterministic, well-formed report for offline/stub operation."""
    overall = float(scorecard.get("overall_score", 0.0)) if scorecard else 0.0
    if not overall and evaluations:
        overall = sum(float(e.get("score", 0)) for e in evaluations) / len(evaluations)

    rec = (
        scorecard.get("recommendation")
        if scorecard and scorecard.get("recommendation") in RECOMMENDATIONS
        else _score_to_recommendation(overall)
    )

    # Rank competencies by score for strengths/weaknesses.
    by_score = sorted(
        evaluations, key=lambda e: float(e.get("score", 0)), reverse=True
    )
    strengths = [
        f"{e.get('competency', 'general')}: {e.get('rationale') or 'demonstrated strong capability'}"
        for e in by_score
        if float(e.get("score", 0)) >= 60
    ][:10]
    weaknesses = [
        f"{e.get('competency', 'general')}: {e.get('rationale') or 'room for improvement'}"
        for e in reversed(by_score)
        if float(e.get("score", 0)) < 60
    ][:10]

    candidate_segs = [
        s.get("text", "")
        for s in transcript
        if s.get("speaker", "candidate") == "candidate" and s.get("text")
    ]
    quotes = candidate_segs[:5]
    highlights = [
        f"Covered {e.get('competency', 'general')} (score {e.get('score', 0)})"
        for e in by_score
    ][:10]

    n_segments = len(transcript)
    summary = (
        f"This report summarizes the candidate's performance in '{interview_title}'. "
        f"The interview produced {n_segments} transcript segment(s) and "
        f"{len(evaluations)} competency evaluation(s), yielding an overall score of "
        f"{overall:.1f}/100.\n\n"
        f"Across the assessed competencies the candidate showed {len(strengths)} notable "
        f"strength area(s) and {len(weaknesses)} area(s) for development. "
        f"The weighted scorecard recommendation is '{rec}'.\n\n"
        "This is a deterministic offline report generated without a live language "
        "model. Configure ANTHROPIC_API_KEY for a fully AI-authored narrative."
    )

    return _normalize(
        {
            "executive_summary": summary,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "risk_indicators": (
                ["Overall score below hiring threshold."] if overall < 55 else []
            ),
            "recommended_position": rec,
            "interview_highlights": highlights,
            "notable_quotes": quotes,
            "role_match_percent": overall,
        },
        overall,
    )


async def generate_report(
    llm: LLMClient,
    *,
    interview_title: str,
    job_description: str,
    transcript: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    scorecard: dict[str, Any] | None,
) -> dict[str, Any]:
    """Produce a structured intelligence report dict (the Report.content payload)."""
    overall = float(scorecard.get("overall_score", 0.0)) if scorecard else 0.0
    if not overall and evaluations:
        overall = sum(float(e.get("score", 0)) for e in evaluations) / len(evaluations)

    if isinstance(llm, StubClient):
        return _stub_report(
            interview_title=interview_title,
            transcript=transcript,
            evaluations=evaluations,
            scorecard=scorecard,
        )

    prompt = build_prompt(
        interview_title=interview_title,
        job_description=job_description,
        transcript=transcript,
        evaluations=evaluations,
        scorecard=scorecard,
    )
    try:
        data = await llm.complete_json(system=SYSTEM, prompt=prompt)
        if isinstance(data, dict) and data.get("executive_summary"):
            return _normalize(data, overall)
    except Exception:
        pass

    # Fallback to deterministic stub on any LLM failure / malformed output.
    return _stub_report(
        interview_title=interview_title,
        transcript=transcript,
        evaluations=evaluations,
        scorecard=scorecard,
    )
