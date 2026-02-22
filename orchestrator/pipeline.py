from __future__ import annotations

from datetime import timezone
import re

from orchestrator.config import Settings
from orchestrator.drafting import generate_drafts
from orchestrator.models import PendingReply, ProjectProfile
from orchestrator.ollama_client import OllamaClient
from orchestrator.product_profile import load_project_profile
from orchestrator.providers.base import SocialProvider
from orchestrator.relevance import heuristic_score
from orchestrator.storage import Storage


class OrchestratorService:
    def __init__(
        self,
        settings: Settings,
        provider: SocialProvider,
        storage: Storage,
        ollama: OllamaClient,
    ):
        self.settings = settings
        self.provider = provider
        self.storage = storage
        self.ollama = ollama

    def scan_once(self) -> list[PendingReply]:
        profile = load_project_profile(self.settings.runtime.project_dir)
        queries = self._build_search_queries(profile)
        candidates = self.provider.discover_candidates(queries)

        ranked = []
        for candidate in candidates:
            candidate.relevance_score = heuristic_score(candidate, profile)
            if candidate.relevance_score >= self.settings.runtime.min_heuristic_score:
                ranked.append(candidate)

        ranked.sort(key=lambda c: c.relevance_score, reverse=True)
        selected = ranked[: self.settings.runtime.max_candidates_per_scan]

        created: list[PendingReply] = []
        for candidate in selected:
            if self.storage.has_candidate(candidate.candidate_id):
                continue
            drafts = generate_drafts(
                ollama=self.ollama,
                model=self.settings.ollama.draft_model,
                profile=profile,
                candidate=candidate,
            )
            pending = PendingReply(candidate=candidate, drafts=drafts)
            self.storage.save_pending(pending)
            self.storage.log_action(candidate.candidate_id, "queued", f"score={candidate.relevance_score:.3f}")
            created.append(pending)
        return created

    def approve_pending(self, candidate_id: str, draft_index: int) -> str:
        pending = self.storage.get_pending(candidate_id)
        if pending is None:
            raise ValueError(f"Unknown candidate_id: {candidate_id}")
        if pending.status != "pending":
            raise ValueError(f"Candidate is not pending: {candidate_id} status={pending.status}")
        if draft_index < 1 or draft_index > len(pending.drafts):
            raise ValueError(f"Invalid draft index {draft_index}, expected 1..{len(pending.drafts)}")

        draft = pending.drafts[draft_index - 1]
        dry_run = self.settings.runtime.dry_run_send
        result = self.provider.send_reply(
            provider_post_id=pending.candidate.provider_post_id,
            text=draft.text,
            dry_run=dry_run,
        )
        self.storage.set_status(candidate_id, "sent" if not dry_run else "approved_dry_run")
        self.storage.log_action(candidate_id, "approved", f"draft={draft_index} result={result}")
        return result

    def reject_pending(self, candidate_id: str, reason: str = "") -> None:
        pending = self.storage.get_pending(candidate_id)
        if pending is None:
            raise ValueError(f"Unknown candidate_id: {candidate_id}")
        self.storage.set_status(candidate_id, "rejected")
        self.storage.log_action(candidate_id, "rejected", reason)

    def _build_search_queries(self, profile: ProjectProfile) -> list[str]:
        base_queries = [q.strip() for q in profile.key_phrases if q.strip()]
        if profile.product_name:
            base_queries.append(profile.product_name)

        # Keep a deterministic fallback even when LLM query expansion fails.
        fallback = list(dict.fromkeys(base_queries))[:8]
        if not fallback:
            fallback = [profile.target_audience, "need recommendation", "best tool"]

        expansion_prompt = f"""Generate up to 8 Reddit search queries for finding posts where users need help and your
product could be relevant.
Return JSON array of strings only.

Product: {profile.product_name}
Target audience: {profile.target_audience}
Value props: {", ".join(profile.value_props)}
Known phrases: {", ".join(profile.key_phrases)}
"""
        try:
            expanded = self.ollama.json_chat(
                model=self.settings.ollama.triage_model,
                system="You generate search queries for social listening. Return JSON only.",
                prompt=expansion_prompt,
                temperature=0.1,
                fallback=fallback,
            )
            if not isinstance(expanded, list):
                return fallback
            cleaned = []
            for q in expanded:
                if not isinstance(q, str):
                    continue
                normalized = re.sub(r"\s+", " ", q).strip()
                if normalized:
                    cleaned.append(normalized[:120])
            merged = list(dict.fromkeys(cleaned + fallback))
            return merged[:8]
        except Exception:
            return fallback

    def format_candidate_for_message(self, pending: PendingReply) -> str:
        c = pending.candidate
        created = c.created_utc.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        top = pending.drafts[0] if pending.drafts else None
        lines = [
            f"ID: {c.candidate_id}",
            f"Score: {c.relevance_score:.3f}",
            f"Author: u/{c.author}",
            f"Created: {created}",
            f"Title: {c.title}",
            f"URL: {c.permalink}",
        ]
        if top is not None:
            lines.append("")
            lines.append(f"Draft 1 ({top.label}):")
            lines.append(top.text)
        lines.append("")
        lines.append("Commands: /show <id> | /approve <id> <1|2|3> | /reject <id>")
        return "\n".join(lines)

    def format_full_drafts(self, candidate_id: str) -> str:
        pending = self.storage.get_pending(candidate_id)
        if pending is None:
            raise ValueError(f"Unknown candidate_id: {candidate_id}")
        payload = []
        for idx, d in enumerate(pending.drafts, start=1):
            payload.append(f"{idx}. [{d.label}] {d.text}\nReason: {d.reason}")
        return "\n\n".join(payload)
