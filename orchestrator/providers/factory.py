from __future__ import annotations

from orchestrator.config import Settings
from orchestrator.providers.base import SocialProvider
from orchestrator.providers.reddit import RedditProvider


def build_provider(settings: Settings) -> SocialProvider:
    provider = settings.runtime.provider.strip().lower()
    if provider == "reddit":
        return RedditProvider(settings.reddit)
    raise ValueError(f"Unsupported provider: {settings.runtime.provider}")

