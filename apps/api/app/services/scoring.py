"""Role-weighted competency scoring.

Pure, deterministic functions that turn a set of per-competency Evaluation
scores (0..100) plus a Position's scoring_weights into a weighted overall score,
a per-competency breakdown, and a hiring recommendation enum.

Kept free of DB/HTTP concerns so it is trivially unit-testable; the router
(app/api/scoring.py) is the only place that touches SQLAlchemy.
"""
from __future__ import annotations

import enum
from collections import defaultdict
from dataclasses import dataclass


class Recommendation(str, enum.Enum):
    strong_hire = "strong_hire"
    hire = "hire"
    consider = "consider"
    weak_hire = "weak_hire"
    reject = "reject"


# Default competency weighting profiles by role-type. Weights sum to 1.0.
TECHNICAL_WEIGHTS: dict[str, float] = {
    "technical": 0.5,
    "problem_solving": 0.2,
    "communication": 0.15,
    "leadership": 0.075,
    "culture_fit": 0.075,
}

NON_TECHNICAL_WEIGHTS: dict[str, float] = {
    "communication": 0.35,
    "problem_solving": 0.25,
    "leadership": 0.2,
    "culture_fit": 0.15,
    "technical": 0.05,
}

# Concrete example from the design spec (Senior Data Engineer).
DATA_ENGINEER_WEIGHTS: dict[str, float] = {
    "technical": 0.6,
    "communication": 0.1,
    "problem_solving": 0.2,
    "leadership": 0.05,
    "culture_fit": 0.05,
}

# overall_score (0..100) -> recommendation, evaluated highest threshold first.
_RECOMMENDATION_THRESHOLDS: list[tuple[float, Recommendation]] = [
    (85.0, Recommendation.strong_hire),
    (70.0, Recommendation.hire),
    (55.0, Recommendation.consider),
    (40.0, Recommendation.weak_hire),
    (0.0, Recommendation.reject),
]


@dataclass
class ScoringResult:
    overall_score: float
    competency_scores: dict[str, dict[str, float]]
    recommendation: Recommendation


def default_weights(is_technical: bool) -> dict[str, float]:
    """Default weight profile for a role-type."""
    return dict(TECHNICAL_WEIGHTS if is_technical else NON_TECHNICAL_WEIGHTS)


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Drop non-positive weights and rescale the remainder to sum to 1.0."""
    positive = {k: float(v) for k, v in weights.items() if v and float(v) > 0}
    total = sum(positive.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in positive.items()}


def aggregate_competencies(
    evaluations: list[tuple[str, float]],
) -> dict[str, float]:
    """Average the 0..100 scores per competency.

    `evaluations` is a list of (competency, score) pairs (one per Evaluation row).
    """
    buckets: dict[str, list[float]] = defaultdict(list)
    for competency, score in evaluations:
        buckets[competency].append(float(score))
    return {c: sum(vals) / len(vals) for c, vals in buckets.items() if vals}


def recommend(overall_score: float) -> Recommendation:
    for threshold, rec in _RECOMMENDATION_THRESHOLDS:
        if overall_score >= threshold:
            return rec
    return Recommendation.reject


def compute_score(
    evaluations: list[tuple[str, float]],
    weights: dict[str, float] | None,
    *,
    is_technical: bool = True,
) -> ScoringResult:
    """Compute a weighted scorecard.

    - Averages evaluation scores per competency.
    - Applies the given `weights` (falling back to a role-type default when the
      position has none), considering only competencies that were actually
      evaluated, and renormalizing those weights so they sum to 1.0.
    - Produces an overall 0..100 score and a recommendation.

    The breakdown reports, per competency: the raw averaged `score`, the
    `weight` actually applied, and its `contribution` to the overall score.
    """
    per_competency = aggregate_competencies(evaluations)

    profile = weights if weights else default_weights(is_technical)

    # Only weight competencies we have data for; renormalize over those.
    applicable = {c: profile[c] for c in per_competency if c in profile}
    norm = normalize_weights(applicable)

    if not norm:
        # No overlap between weights and evaluated competencies: fall back to a
        # plain average so we still produce a usable score.
        evaluated = list(per_competency.values())
        overall = sum(evaluated) / len(evaluated) if evaluated else 0.0
        breakdown = {
            c: {"score": round(s, 2), "weight": 0.0, "contribution": 0.0}
            for c, s in per_competency.items()
        }
        return ScoringResult(
            overall_score=round(overall, 2),
            competency_scores=breakdown,
            recommendation=recommend(overall),
        )

    breakdown: dict[str, dict[str, float]] = {}
    overall = 0.0
    for competency, score in per_competency.items():
        weight = norm.get(competency, 0.0)
        contribution = score * weight
        overall += contribution
        breakdown[competency] = {
            "score": round(score, 2),
            "weight": round(weight, 4),
            "contribution": round(contribution, 2),
        }

    overall = round(overall, 2)
    return ScoringResult(
        overall_score=overall,
        competency_scores=breakdown,
        recommendation=recommend(overall),
    )
