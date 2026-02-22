from __future__ import annotations

from abc import ABC, abstractmethod

from orchestrator.models import PostCandidate


class SocialProvider(ABC):
    name: str

    @abstractmethod
    def discover_candidates(self, search_queries: list[str]) -> list[PostCandidate]:
        raise NotImplementedError

    @abstractmethod
    def send_reply(self, provider_post_id: str, text: str, dry_run: bool = False) -> str:
        raise NotImplementedError

