from __future__ import annotations

import argparse
import sys

from orchestrator.config import load_settings
from orchestrator.ollama_client import OllamaClient
from orchestrator.pipeline import OrchestratorService
from orchestrator.providers.factory import build_provider
from orchestrator.storage import Storage
from orchestrator.telegram_bot import TelegramControlBot


def build_service(config_path: str | None) -> tuple[OrchestratorService, Storage]:
    settings = load_settings(config_path)
    storage = Storage(settings.runtime.db_path)
    provider = build_provider(settings)
    ollama = OllamaClient(settings.ollama.host)
    service = OrchestratorService(settings=settings, provider=provider, storage=storage, ollama=ollama)
    return service, storage


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agora local orchestrator")
    parser.add_argument("--config", default=None, help="Path to settings.toml")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bot", help="Run Telegram bot + periodic scan loop")
    sub.add_parser("scan", help="Run one scan and print IDs")
    sub.add_parser("list", help="List pending candidates")

    show = sub.add_parser("show", help="Show drafts for a candidate")
    show.add_argument("candidate_id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv or sys.argv[1:])
    service, storage = build_service(args.config)

    if args.command == "bot":
        settings = load_settings(args.config)
        bot = TelegramControlBot(settings.telegram, service, storage)
        bot.run()
        return

    if args.command == "scan":
        created = service.scan_once()
        if not created:
            print("No new candidates found.")
            return
        print(f"Created {len(created)} pending candidates:")
        for p in created:
            print(f"- {p.candidate.candidate_id} score={p.candidate.relevance_score:.3f}")
        return

    if args.command == "list":
        pending = storage.list_pending(30)
        if not pending:
            print("No pending candidates.")
            return
        for p in pending:
            print(f"{p.candidate.candidate_id} score={p.candidate.relevance_score:.3f}")
        return

    if args.command == "show":
        print(service.format_full_drafts(args.candidate_id))
        return

    raise RuntimeError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
