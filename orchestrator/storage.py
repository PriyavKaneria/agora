from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import sqlite3

from orchestrator.models import DraftVariant, PendingReply, PostCandidate


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(raw: str) -> datetime:
    return datetime.fromisoformat(raw)


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS pending_replies (
                    candidate_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    provider_post_id TEXT NOT NULL,
                    permalink TEXT NOT NULL,
                    author TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_utc TEXT NOT NULL,
                    relevance_score REAL NOT NULL,
                    metadata_json TEXT NOT NULL,
                    drafts_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    inserted_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

    def has_candidate(self, candidate_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM pending_replies WHERE candidate_id = ?", (candidate_id,)).fetchone()
            return row is not None

    def save_pending(self, pending: PendingReply) -> None:
        c = pending.candidate
        drafts_json = json.dumps([asdict(d) for d in pending.drafts], ensure_ascii=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO pending_replies (
                    candidate_id, provider, provider_post_id, permalink, author, title, body, created_utc,
                    relevance_score, metadata_json, drafts_json, status, inserted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    c.candidate_id,
                    c.provider,
                    c.provider_post_id,
                    c.permalink,
                    c.author,
                    c.title,
                    c.body,
                    _to_iso(c.created_utc),
                    c.relevance_score,
                    json.dumps(c.metadata, ensure_ascii=True),
                    drafts_json,
                    pending.status,
                    _to_iso(pending.created_at),
                ),
            )

    def list_pending(self, limit: int = 20) -> list[PendingReply]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pending_replies
                WHERE status = 'pending'
                ORDER BY relevance_score DESC, inserted_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_pending(r) for r in rows]

    def get_pending(self, candidate_id: str) -> PendingReply | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM pending_replies WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_pending(row)

    def set_status(self, candidate_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE pending_replies SET status = ? WHERE candidate_id = ?",
                (status, candidate_id),
            )

    def log_action(self, candidate_id: str, action: str, detail: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO actions (candidate_id, action, detail, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (candidate_id, action, detail, _to_iso(datetime.now(timezone.utc))),
            )

    def _row_to_pending(self, row: sqlite3.Row) -> PendingReply:
        candidate = PostCandidate(
            provider=row["provider"],
            provider_post_id=row["provider_post_id"],
            permalink=row["permalink"],
            author=row["author"],
            title=row["title"],
            body=row["body"],
            created_utc=_from_iso(row["created_utc"]),
            metadata=json.loads(row["metadata_json"]),
            relevance_score=float(row["relevance_score"]),
        )
        drafts = [DraftVariant(**d) for d in json.loads(row["drafts_json"])]
        return PendingReply(
            candidate=candidate,
            drafts=drafts,
            created_at=_from_iso(row["inserted_at"]),
            status=row["status"],
        )

