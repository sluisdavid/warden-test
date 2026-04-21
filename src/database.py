from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _resolve_db_path(database_url: str) -> str:
    if database_url.startswith("file:"):
        parsed = urlparse(database_url)
        raw_path = parsed.path or database_url.removeprefix("file:")
        if raw_path.startswith("/") and ":" in raw_path:
            raw_path = raw_path.lstrip("/")
        if not raw_path:
            raw_path = "warden.db"
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)
    path = Path(database_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


class Database:
    def __init__(self, database_url: str) -> None:
        self.database_path = _resolve_db_path(database_url)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.database_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    environment_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    event_timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    llm_decision_json TEXT,
                    approval_id TEXT,
                    action_result TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(event_id) REFERENCES events(id)
                );

                CREATE INDEX IF NOT EXISTS idx_events_workload_time
                    ON events(project_id, environment_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_approvals_status
                    ON approvals(status, created_at DESC);
                """
            )
