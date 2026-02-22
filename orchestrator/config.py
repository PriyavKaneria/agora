from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib


@dataclass(slots=True)
class OllamaConfig:
    host: str = "http://127.0.0.1:11434"
    triage_model: str = "llama3.1:8b"
    draft_model: str = "llama3.1:8b"


@dataclass(slots=True)
class RedditConfig:
    client_id: str = ""
    client_secret: str = ""
    username: str = ""
    password: str = ""
    user_agent: str = "agora-orchestrator/0.1"
    subreddits: list[str] = field(default_factory=lambda: ["all"])
    limit_per_query: int = 15
    lookback_hours: int = 24


@dataclass(slots=True)
class TelegramConfig:
    bot_token: str = ""
    allowed_chat_ids: list[int] = field(default_factory=list)
    scan_interval_minutes: int = 20


@dataclass(slots=True)
class RuntimeConfig:
    provider: str = "reddit"
    db_path: str = "agora.db"
    project_dir: str = "products/default"
    max_candidates_per_scan: int = 5
    min_heuristic_score: float = 0.15
    dry_run_send: bool = True


@dataclass(slots=True)
class Settings:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    reddit: RedditConfig = field(default_factory=RedditConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)


def _get_nested(data: dict, path: list[str], default):
    node = data
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def _as_int_list(raw: object) -> list[int]:
    if isinstance(raw, list):
        return [int(v) for v in raw]
    return []


def load_settings(config_path: str | None = None) -> Settings:
    path = Path(config_path or os.environ.get("AGORA_CONFIG", "config/settings.toml"))
    data: dict = {}
    if path.exists():
        with path.open("rb") as f:
            data = tomllib.load(f)

    ollama = OllamaConfig(
        host=os.environ.get("OLLAMA_HOST", _get_nested(data, ["ollama", "host"], "http://127.0.0.1:11434")),
        triage_model=os.environ.get(
            "OLLAMA_TRIAGE_MODEL", _get_nested(data, ["ollama", "triage_model"], "llama3.1:8b")
        ),
        draft_model=os.environ.get(
            "OLLAMA_DRAFT_MODEL", _get_nested(data, ["ollama", "draft_model"], "llama3.1:8b")
        ),
    )

    reddit = RedditConfig(
        client_id=os.environ.get("REDDIT_CLIENT_ID", _get_nested(data, ["reddit", "client_id"], "")),
        client_secret=os.environ.get("REDDIT_CLIENT_SECRET", _get_nested(data, ["reddit", "client_secret"], "")),
        username=os.environ.get("REDDIT_USERNAME", _get_nested(data, ["reddit", "username"], "")),
        password=os.environ.get("REDDIT_PASSWORD", _get_nested(data, ["reddit", "password"], "")),
        user_agent=os.environ.get(
            "REDDIT_USER_AGENT", _get_nested(data, ["reddit", "user_agent"], "agora-orchestrator/0.1")
        ),
        subreddits=_get_nested(data, ["reddit", "subreddits"], ["all"]),
        limit_per_query=int(_get_nested(data, ["reddit", "limit_per_query"], 15)),
        lookback_hours=int(_get_nested(data, ["reddit", "lookback_hours"], 24)),
    )

    telegram = TelegramConfig(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", _get_nested(data, ["telegram", "bot_token"], "")),
        allowed_chat_ids=_as_int_list(_get_nested(data, ["telegram", "allowed_chat_ids"], [])),
        scan_interval_minutes=int(_get_nested(data, ["telegram", "scan_interval_minutes"], 20)),
    )

    runtime = RuntimeConfig(
        provider=str(_get_nested(data, ["runtime", "provider"], "reddit")),
        db_path=os.environ.get("AGORA_DB_PATH", _get_nested(data, ["runtime", "db_path"], "agora.db")),
        project_dir=os.environ.get("AGORA_PROJECT_DIR", _get_nested(data, ["runtime", "project_dir"], "products/default")),
        max_candidates_per_scan=int(_get_nested(data, ["runtime", "max_candidates_per_scan"], 5)),
        min_heuristic_score=float(_get_nested(data, ["runtime", "min_heuristic_score"], 0.15)),
        dry_run_send=str(_get_nested(data, ["runtime", "dry_run_send"], True)).lower() in ("1", "true", "yes"),
    )

    return Settings(ollama=ollama, reddit=reddit, telegram=telegram, runtime=runtime)
