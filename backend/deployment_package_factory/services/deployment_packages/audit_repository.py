from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from deployment_package_factory.services.deployment_packages.models import AuditEvent
from deployment_package_factory.services.deployment_packages.task_repository import DEFAULT_TASK_DB


DEFAULT_AUDIT_DB = DEFAULT_TASK_DB.with_name("deployment-package-audit.sqlite3")


class AuditEventRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_AUDIT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def record(
        self,
        *,
        action: str,
        status: str,
        target_id: str = "",
        operator: str = "",
        client_ip: str = "",
        message: str = "",
        metadata: dict | None = None,
    ) -> AuditEvent:
        now = datetime.now(timezone.utc).isoformat()
        event = AuditEvent(
            eventId=f"audit-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            action=action,
            targetId=target_id,
            status=status,
            operator=operator,
            clientIp=client_ip,
            message=message,
            metadata=metadata or {},
            createdAt=now,
        )
        with self._connect() as conn:
            conn.execute(
                """
                insert into audit_events(
                    event_id, action, target_id, status, operator, client_ip,
                    message, metadata_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _event_to_row(event),
            )
        return event

    def list(self, limit: int = 100) -> list[AuditEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from audit_events order by created_at desc limit ?",
                (max(1, min(500, limit)),),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def metrics_summary(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("select count(*) as count from audit_events").fetchone()["count"]
            action_rows = conn.execute(
                "select action, count(*) as count from audit_events group by action"
            ).fetchall()
        return {
            "total": total,
            "byAction": {row["action"]: row["count"] for row in action_rows},
        }

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists audit_events (
                    event_id text primary key,
                    action text not null,
                    target_id text not null,
                    status text not null,
                    operator text not null,
                    client_ip text not null,
                    message text not null,
                    metadata_json text not null,
                    created_at text not null
                )
                """
            )
            conn.execute("create index if not exists idx_audit_events_created_at on audit_events(created_at)")
            conn.execute("create index if not exists idx_audit_events_action on audit_events(action)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def _event_to_row(event: AuditEvent) -> tuple:
    return (
        event.event_id,
        event.action,
        event.target_id,
        event.status,
        event.operator,
        event.client_ip,
        event.message,
        json.dumps(event.metadata, ensure_ascii=False),
        event.created_at,
    )


def _event_from_row(row: sqlite3.Row) -> AuditEvent:
    return AuditEvent(
        eventId=row["event_id"],
        action=row["action"],
        targetId=row["target_id"],
        status=row["status"],
        operator=row["operator"],
        clientIp=row["client_ip"],
        message=row["message"],
        metadata=json.loads(row["metadata_json"]),
        createdAt=row["created_at"],
    )
