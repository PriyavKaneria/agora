from __future__ import annotations

from orchestrator.models import DraftVariant, PostCandidate, ProjectProfile
from orchestrator.ollama_client import OllamaClient


DRAFT_SYSTEM_PROMPT = """You write concise, helpful replies to social posts.
Rules:
- Solve the OP's problem first; avoid spammy language.
- Mention the product naturally only if relevant.
- Keep each draft <= 120 words.
- Never fabricate claims or guarantees.
- Return strict JSON array with 3 objects: label, text, reason.
"""


def _fallback_drafts(profile: ProjectProfile, candidate: PostCandidate) -> list[DraftVariant]:
    product_hint = profile.product_name
    return [
        DraftVariant(
            label="help-first",
            text=(
                f"Sounds frustrating. One approach that often helps is to break this into smaller steps, "
                f"measure what is failing first, and then test one fix at a time. If useful, I can share a "
                f"template I use for this."
            ),
            reason="No LLM output parsed; safe generic help response.",
        ),
        DraftVariant(
            label="soft-mention",
            text=(
                f"I had a similar issue and found that a repeatable workflow made the biggest difference. "
                f"I've been using {product_hint} for this, but even without it, tracking the same steps each time helps."
            ),
            reason="Gentle product mention with practical value.",
        ),
        DraftVariant(
            label="direct-cta",
            text=(
                f"If you want, I can send a quick walkthrough. {product_hint} is built specifically for this use case "
                f"and might save you trial-and-error."
            ),
            reason="Direct but still opt-in CTA.",
        ),
    ]


def generate_drafts(
    ollama: OllamaClient,
    model: str,
    profile: ProjectProfile,
    candidate: PostCandidate,
) -> list[DraftVariant]:
    prompt = f"""Product profile:
Product: {profile.product_name}
Audience: {profile.target_audience}
Value props: {", ".join(profile.value_props) if profile.value_props else "n/a"}
Forbidden claims: {", ".join(profile.forbidden_claims) if profile.forbidden_claims else "n/a"}

Social post:
Title: {candidate.title}
Body: {candidate.body[:2500]}
URL: {candidate.permalink}

Generate 3 draft replies in JSON array format.
"""
    payload = ollama.json_chat(
        model=model,
        system=DRAFT_SYSTEM_PROMPT,
        prompt=prompt,
        temperature=0.3,
        fallback=None,
    )

    if not isinstance(payload, list):
        return _fallback_drafts(profile, candidate)

    drafts: list[DraftVariant] = []
    for item in payload[:3]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "draft")).strip()[:32]
        text = str(item.get("text", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if text:
            drafts.append(DraftVariant(label=label or "draft", text=text[:800], reason=reason[:200]))

    if len(drafts) < 3:
        fallback = _fallback_drafts(profile, candidate)
        drafts.extend(fallback[len(drafts) :])

    return drafts[:3]

