from __future__ import annotations

from datetime import datetime, timezone
import math
import re

from orchestrator.models import PostCandidate, ProjectProfile


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]{3,}")


def _tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in TOKEN_RE.finditer(text)}


def _freshness_weight(created_utc: datetime) -> float:
    age_hours = max((datetime.now(timezone.utc) - created_utc).total_seconds() / 3600.0, 0.0)
    return math.exp(-age_hours / 24.0)


def heuristic_score(candidate: PostCandidate, profile: ProjectProfile) -> float:
    candidate_tokens = _tokenize(f"{candidate.title}\n{candidate.body}")
    profile_tokens = _tokenize(
        " ".join(profile.key_phrases + profile.value_props + [profile.product_name, profile.target_audience])
    )
    if not profile_tokens:
        profile_tokens = _tokenize(profile.product_name)

    overlap = 0.0
    if profile_tokens:
        overlap = len(candidate_tokens.intersection(profile_tokens)) / len(profile_tokens)

    intent_tokens = {"help", "recommend", "tool", "solution", "looking", "need", "struggling", "advice"}
    intent_overlap = len(candidate_tokens.intersection(intent_tokens)) / len(intent_tokens)
    freshness = _freshness_weight(candidate.created_utc)

    return (0.65 * overlap) + (0.20 * intent_overlap) + (0.15 * freshness)

