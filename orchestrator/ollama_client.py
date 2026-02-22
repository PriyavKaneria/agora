from __future__ import annotations

import json
from typing import Any

import httpx


class OllamaClient:
    def __init__(self, host: str):
        self.host = host.rstrip("/")

    def chat(self, model: str, system: str, prompt: str, temperature: float = 0.2) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": temperature},
            "stream": False,
        }
        with httpx.Client(timeout=90.0) as client:
            response = client.post(f"{self.host}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        message = data.get("message", {})
        content = message.get("content")
        if not isinstance(content, str):
            raise RuntimeError("Unexpected Ollama response format from /api/chat")
        return content.strip()

    def json_chat(
        self,
        model: str,
        system: str,
        prompt: str,
        temperature: float = 0.2,
        fallback: Any | None = None,
    ) -> Any:
        raw = self.chat(model=model, system=system, prompt=prompt, temperature=temperature)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if fallback is not None:
                return fallback
            raise

