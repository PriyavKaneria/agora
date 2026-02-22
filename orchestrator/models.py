from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ProjectProfile:
    project_id: str
    product_name: str
    target_audience: str
    value_props: list[str]
    key_phrases: list[str]
    forbidden_claims: list[str]
    source_notes: str
    image_paths: list[str]


@dataclass(slots=True)
class PostCandidate:
    provider: str
    provider_post_id: str
    permalink: str
    author: str
    title: str
    body: str
    created_utc: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0

    @property
    def candidate_id(self) -> str:
        return f"{self.provider}:{self.provider_post_id}"


@dataclass(slots=True)
class DraftVariant:
    label: str
    text: str
    reason: str


@dataclass(slots=True)
class PendingReply:
    candidate: PostCandidate
    drafts: list[DraftVariant]
    created_at: datetime = field(default_factory=utc_now)
    status: str = "pending"

