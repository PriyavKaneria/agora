# Agora Orchestrator (Reddit + Ollama + Telegram)

Local-first outreach orchestrator that:
- Ingests product docs from a folder.
- Finds potentially relevant Reddit posts.
- Ranks candidates and drafts replies with local Ollama models.
- Sends candidates to Telegram for human approval.
- Posts to Reddit only on explicit `/approve`.

## 1) Setup

### Prerequisites
- Python 3.11+
- Ollama running locally
- Reddit app credentials + account
- Telegram bot token

### Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Configure
```bash
mkdir -p config
cp config/settings.example.toml config/settings.toml
```

Edit `config/settings.toml`:
- Set `runtime.provider = "reddit"` for this MVP.
- Fill `reddit.*` credentials.
- Fill `telegram.bot_token`.
- Optionally add `telegram.allowed_chat_ids` (recommended).
- Set `runtime.project_dir` to your product folder.
- Keep `runtime.dry_run_send = true` until you validate behavior.

### Prepare product profile
Place content under `products/default` (or your configured folder):
- `profile.toml` for structured metadata.
- Markdown/text notes for deep context.
- Product images.

## 2) Run

### One scan from CLI
```bash
agora --config config/settings.toml scan
```

### Run Telegram control bot (recommended)
```bash
agora --config config/settings.toml bot
```

Bot commands:
- `/chatid`
- `/scan`
- `/list`
- `/show <candidate_id>`
- `/approve <candidate_id> <1|2|3>`
- `/reject <candidate_id>`

## 3) Safety Model

- No automatic posting flow exists.
- Every post requires a manual `/approve`.
- `dry_run_send=true` prevents real posting even on approval.
- Audit logs are persisted in SQLite (`runtime.db_path`).

## 4) Storage

SQLite tables:
- `pending_replies`: candidate + drafts + status.
- `actions`: queue/approve/reject action logs.

## 5) Extension Points

The provider contract is in `orchestrator/providers/base.py`.

To add more platforms:
1. Implement `discover_candidates(...)`.
2. Implement `send_reply(...)`.
3. Register provider selection in `orchestrator/providers/factory.py`.

## 6) Operational Notes

- For always-on operation, run `agora ... bot` via `launchd` (macOS) or system supervisor.
- If `allowed_chat_ids` is empty, periodic scans are disabled for push notifications, but manual `/scan` still works.
