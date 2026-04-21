from __future__ import annotations

import json
from datetime import datetime, timezone

from src.database import Database
from src.schemas import ApprovalRecord, EventRecord, HistoryItem, LLMDecision


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, event: EventRecord) -> EventRecord:
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO events (
                    id, project_id, environment_id, severity, signal, context_json,
                    event_timestamp, status, llm_decision_json, approval_id,
                    action_result, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.project_id,
                    event.environment_id,
                    event.severity.value,
                    event.signal,
                    json.dumps(event.context),
                    event.timestamp.isoformat(),
                    event.status,
                    json.dumps(event.llm_decision.model_dump()) if event.llm_decision else None,
                    event.approval_id,
                    event.action_result,
                    event.created_at.isoformat(),
                    event.updated_at.isoformat(),
                ),
            )
        return event

    def update(self, event: EventRecord) -> EventRecord:
        with self.db.connection() as conn:
            conn.execute(
                """
                UPDATE events
                SET status = ?, llm_decision_json = ?, approval_id = ?, action_result = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    event.status,
                    json.dumps(event.llm_decision.model_dump()) if event.llm_decision else None,
                    event.approval_id,
                    event.action_result,
                    event.updated_at.isoformat(),
                    event.id,
                ),
            )
        return event

    def list(self) -> list[EventRecord]:
        with self.db.connection() as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY created_at DESC").fetchall()
        return [self._map_event(row) for row in rows]

    def get(self, event_id: str) -> EventRecord | None:
        with self.db.connection() as conn:
            row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return self._map_event(row) if row else None

    def history(self, project_id: str, environment_id: str, limit: int) -> list[HistoryItem]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE project_id = ? AND environment_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, environment_id, limit),
            ).fetchall()
        items: list[HistoryItem] = []
        for row in rows:
            decision = json.loads(row["llm_decision_json"]) if row["llm_decision_json"] else {}
            feedback = None
            if row["approval_id"]:
                with self.db.connection() as conn:
                    approval = conn.execute(
                        "SELECT status FROM approvals WHERE id = ?",
                        (row["approval_id"],),
                    ).fetchone()
                if approval:
                    feedback = approval["status"]
            items.append(
                HistoryItem(
                    event_id=row["id"],
                    signal=row["signal"],
                    llm_action=decision.get("action"),
                    llm_confidence=decision.get("confidence"),
                    llm_safe_to_auto=decision.get("safe_to_auto"),
                    execution_state=row["status"],
                    result=row["action_result"],
                    feedback=feedback,
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )
        return items

    @staticmethod
    def _map_event(row) -> EventRecord:
        return EventRecord(
            id=row["id"],
            project_id=row["project_id"],
            environment_id=row["environment_id"],
            severity=row["severity"],
            signal=row["signal"],
            context=json.loads(row["context_json"]),
            timestamp=datetime.fromisoformat(row["event_timestamp"]),
            status=row["status"],
            llm_decision=LLMDecision.model_validate(json.loads(row["llm_decision_json"])) if row["llm_decision_json"] else None,
            approval_id=row["approval_id"],
            action_result=row["action_result"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class ApprovalRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, approval: ApprovalRecord) -> ApprovalRecord:
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO approvals (id, event_id, action, status, requested_reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.id,
                    approval.event_id,
                    approval.action.value,
                    approval.status,
                    approval.requested_reason,
                    approval.created_at.isoformat(),
                    approval.updated_at.isoformat(),
                ),
            )
        return approval

    def update_status(self, approval_id: str, status: str) -> ApprovalRecord | None:
        current = self.get(approval_id)
        if not current:
            return None
        updated = current.model_copy(update={"status": status, "updated_at": datetime.now(timezone.utc)})
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE approvals SET status = ?, updated_at = ? WHERE id = ?",
                (updated.status, updated.updated_at.isoformat(), approval_id),
            )
        return updated

    def get(self, approval_id: str) -> ApprovalRecord | None:
        with self.db.connection() as conn:
            row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        return self._map_approval(row) if row else None

    def list_pending(self) -> list[ApprovalRecord]:
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE status = 'pending' ORDER BY created_at DESC"
            ).fetchall()
        return [self._map_approval(row) for row in rows]

    @staticmethod
    def _map_approval(row) -> ApprovalRecord:
        return ApprovalRecord(
            id=row["id"],
            event_id=row["event_id"],
            action=row["action"],
            status=row["status"],
            requested_reason=row["requested_reason"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
