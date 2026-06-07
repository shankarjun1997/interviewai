"""Candidate Ranking Engine.

Deterministic numeric ranking derived purely from Scorecard data (overall_score
+ competency_scores). The LLM is used ONLY for the narrative hiring
recommendation and never influences ordering. A deterministic stub fallback
(StubClient) keeps the whole flow runnable offline.

Dimensions ranked: technical, communication, problem_solving, leadership.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.services.llm import LLMClient

# Canonical per-dimension rankings we always emit.
DIMENSIONS = ("technical", "communication", "problem_solving", "leadership")


@dataclass
class CandidateScores:
    """Normalized view of one candidate's scorecard for ranking."""

    interview_id: str
    scorecard_id: str
    candidate_id: str | None
    candidate_name: str
    overall_score: float
    competency_scores: dict
    recommendation: str


@dataclass
class RankedEntry:
    rank: int
    interview_id: str
    scorecard_id: str
    candidate_id: str | None
    candidate_name: str
    score: float


@dataclass
class RankingResult:
    overall: list[RankedEntry]
    dimensions: dict[str, list[RankedEntry]] = field(default_factory=dict)
    recommendation: str = ""


def _competency_value(scores: dict, dimension: str) -> float:
    """Pull a dimension score from competency_scores.

    competency_scores values may be a plain number or a dict like
    {"score": 80, "rationale": "..."}. Missing dimensions => 0.0.
    """
    raw = scores.get(dimension)
    if raw is None:
        return 0.0
    if isinstance(raw, dict):
        raw = raw.get("score", 0.0)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _rank_by(
    candidates: list[CandidateScores], key
) -> list[RankedEntry]:
    """Deterministic descending sort.

    Ties are broken by candidate_name then interview_id so the ordering is
    stable and reproducible regardless of input order.
    """
    ordered = sorted(
        candidates,
        key=lambda c: (-key(c), c.candidate_name.lower(), c.interview_id),
    )
    return [
        RankedEntry(
            rank=i + 1,
            interview_id=c.interview_id,
            scorecard_id=c.scorecard_id,
            candidate_id=c.candidate_id,
            candidate_name=c.candidate_name,
            score=round(key(c), 4),
        )
        for i, c in enumerate(ordered)
    ]


def rank_candidates(candidates: list[CandidateScores]) -> tuple[list[RankedEntry], dict[str, list[RankedEntry]]]:
    """Pure, deterministic ranking. No I/O, no LLM."""
    overall = _rank_by(candidates, lambda c: c.overall_score)
    dimensions = {
        dim: _rank_by(candidates, lambda c, d=dim: _competency_value(c.competency_scores, d))
        for dim in DIMENSIONS
    }
    return overall, dimensions


def _stub_recommendation(overall: list[RankedEntry]) -> str:
    if not overall:
        return "No scorecards available to rank."
    top = overall[0]
    lines = [
        f"Recommended hire: {top.candidate_name} (overall {top.score}).",
        "Ranking (overall):",
    ]
    for e in overall:
        lines.append(f"  {e.rank}. {e.candidate_name} — {e.score}")
    return "\n".join(lines)


async def generate_recommendation(
    llm: LLMClient,
    overall: list[RankedEntry],
    dimensions: dict[str, list[RankedEntry]],
) -> str:
    """LLM narrative summary. Falls back to deterministic stub text offline.

    The LLM never changes the ordering; we pass the already-computed ranking
    and ask only for prose. If the client is the offline stub (or returns the
    stub sentinel / unusable output), we synthesize a deterministic summary.
    """
    if not overall:
        return _stub_recommendation(overall)

    ranking_payload = {
        "overall": [
            {"rank": e.rank, "name": e.candidate_name, "score": e.score} for e in overall
        ],
        "dimensions": {
            dim: [
                {"rank": e.rank, "name": e.candidate_name, "score": e.score}
                for e in entries
            ]
            for dim, entries in dimensions.items()
        },
    }

    system = (
        "You are a hiring panel assistant. Given a precomputed, fixed candidate "
        "ranking, write a concise hiring recommendation. Do NOT change the order."
    )
    prompt = (
        "Precomputed ranking (authoritative, do not reorder):\n"
        + json.dumps(ranking_payload, indent=2)
        + "\n\nWrite a short recommendation naming the top candidate and the key "
        "differentiators per dimension."
    )

    try:
        raw = await llm.complete(system=system, prompt=prompt, max_tokens=512)
    except Exception:
        return _stub_recommendation(overall)

    text = (raw or "").strip()
    # StubClient returns a JSON sentinel with "stub": true — detect & fall back.
    if not text:
        return _stub_recommendation(overall)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get("stub"):
            return _stub_recommendation(overall)
    except (json.JSONDecodeError, ValueError):
        pass  # real prose, use as-is
    return text
