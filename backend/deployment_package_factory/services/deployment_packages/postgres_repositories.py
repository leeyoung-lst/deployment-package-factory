from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator, TypeVar
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from deployment_package_factory.services.deployment_packages.models import (
    AuditEvent,
    PackageBuildRequest,
    PackageBuildResult,
    PackageTask,
    TaskStatus,
)
from deployment_package_factory.services.deployment_packages.task_repository import _artifact_available, _parse_iso

T = TypeVar("T")


class PostgresPackageTaskRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._ensure_schema()

    def create(self, request: PackageBuildRequest) -> PackageTask:
        now = _now_iso()
        task = PackageTask(
            taskId=f"task-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            status="pending",
            progress=0,
            message="等待执行",
            request=request.model_dump(by_alias=True),
            result=None,
            artifactAvailable=False,
            error="",
            logs=["任务已创建"],
            createdAt=now,
            updatedAt=now,
        )
        with self._connect() as conn:
            conn.execute(
                """
                insert into package_tasks(
                    task_id, status, progress, message, request_json, result_json,
                    error, logs_json, worker_id, claimed_at, heartbeat_at, created_at, updated_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                _task_to_row(task),
            )
        return task

    def get(self, task_id: str) -> PackageTask | None:
        with self._connect() as conn:
            row = conn.execute("select * from package_tasks where task_id = %s", (task_id,)).fetchone()
        return _task_from_row(row) if row else None

    def list(self, limit: int = 50) -> list[PackageTask]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from package_tasks order by created_at desc limit %s",
                (limit,),
            ).fetchall()
        return [_task_from_row(row) for row in rows]

    def metrics_summary(self) -> dict:
        with self._connect() as conn:
            status_rows = conn.execute(
                "select status, count(*) as count from package_tasks group by status"
            ).fetchall()
            total = conn.execute("select count(*) as count from package_tasks").fetchone()["count"]
            artifact_rows = conn.execute(
                """
                select result_json from package_tasks
                where status = 'completed' and result_json is not null
                """
            ).fetchall()
        artifact_bytes = 0
        available_artifacts = 0
        for row in artifact_rows:
            result = PackageBuildResult.model_validate_json(row["result_json"])
            artifact = Path(result.artifact_path)
            if artifact.is_file():
                available_artifacts += 1
                artifact_bytes += artifact.stat().st_size
        return {
            "total": total,
            "byStatus": {row["status"]: row["count"] for row in status_rows},
            "availableArtifacts": available_artifacts,
            "artifactBytes": artifact_bytes,
        }

    def claim_next_pending(self, worker_id: str = "") -> PackageTask | None:
        now = _now_iso()
        with self._connect() as conn:
            row = conn.execute(
                """
                select * from package_tasks
                where status = 'pending'
                order by created_at asc
                limit 1
                for update skip locked
                """
            ).fetchone()
            if row is None:
                return None
            logs = [*json.loads(row["logs_json"]), "Worker 已领取任务"]
            claimed = conn.execute(
                """
                update package_tasks
                set status = %s, progress = %s, message = %s, logs_json = %s,
                    worker_id = %s, claimed_at = %s, heartbeat_at = %s, updated_at = %s
                where task_id = %s
                returning *
                """,
                (
                    "running",
                    8,
                    "Worker 已领取任务，等待执行",
                    json.dumps(logs, ensure_ascii=False),
                    worker_id,
                    now,
                    now,
                    now,
                    row["task_id"],
                ),
            ).fetchone()
        return _task_from_row(claimed) if claimed else None

    def heartbeat(self, task_id: str, worker_id: str = "") -> PackageTask:
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status != "running":
            return task
        if task.worker_id and worker_id and task.worker_id != worker_id:
            raise ValueError(f"Task {task_id} is owned by worker {task.worker_id}.")
        now = _now_iso()
        with self._connect() as conn:
            row = conn.execute(
                """
                update package_tasks
                set heartbeat_at = %s, updated_at = %s
                where task_id = %s and status = 'running'
                returning *
                """,
                (now, now, task_id),
            ).fetchone()
        if row is None:
            raise KeyError(task_id)
        return _task_from_row(row)

    def mark_stale_running_failed(self, timeout_minutes: int) -> list[PackageTask]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, timeout_minutes))
        now = _now_iso()
        updated: list[PackageTask] = []
        with self._connect() as conn:
            rows = conn.execute("select * from package_tasks where status = 'running'").fetchall()
            for row in rows:
                last_seen = _parse_iso(row["heartbeat_at"] or row["updated_at"])
                if last_seen >= cutoff:
                    continue
                error = f"Worker task timed out after {timeout_minutes} minutes."
                logs = [*json.loads(row["logs_json"]), f"部署包生成失败：{error}"]
                updated_row = conn.execute(
                    """
                    update package_tasks
                    set status = %s, progress = %s, message = %s, error = %s, logs_json = %s, updated_at = %s
                    where task_id = %s
                    returning *
                    """,
                    ("failed", 100, "部署包生成失败", error, json.dumps(logs, ensure_ascii=False), now, row["task_id"]),
                ).fetchone()
                if updated_row:
                    updated.append(_task_from_row(updated_row))
        return updated

    def mark_running(self, task_id: str, message: str = "正在生成部署包", worker_id: str = "") -> PackageTask:
        task = self.update(task_id, status="running", progress=10, message=message, log=message)
        if task.worker_id or not worker_id:
            return task
        now = _now_iso()
        with self._connect() as conn:
            row = conn.execute(
                """
                update package_tasks
                set worker_id = %s, claimed_at = %s, heartbeat_at = %s, updated_at = %s
                where task_id = %s
                returning *
                """,
                (worker_id, now, now, now, task_id),
            ).fetchone()
        if row is None:
            raise KeyError(task_id)
        return _task_from_row(row)

    def mark_completed(self, task_id: str, result: PackageBuildResult) -> PackageTask:
        return self.update(
            task_id,
            status="completed",
            progress=100,
            message="部署包生成完成",
            result=result,
            error="",
            log="部署包生成完成",
        )

    def mark_failed(self, task_id: str, error: str) -> PackageTask:
        return self.update(
            task_id,
            status="failed",
            progress=100,
            message="部署包生成失败",
            error=error,
            log=f"部署包生成失败：{error}",
        )

    def cancel(self, task_id: str) -> PackageTask:
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status in {"completed", "failed", "canceled"}:
            raise ValueError(f"Task {task_id} cannot be canceled from status {task.status}.")
        if task.status == "pending":
            return self.update(
                task_id,
                status="canceled",
                progress=100,
                message="部署包任务已取消",
                error="",
                log="部署包任务已取消",
            )
        return self.update(
            task_id,
            message="部署包任务已请求取消，等待当前步骤结束",
            log="部署包任务已请求取消",
        )

    def retry(self, task_id: str) -> PackageTask:
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status not in {"failed", "canceled"}:
            raise ValueError(f"Task {task_id} cannot be retried from status {task.status}.")
        request = PackageBuildRequest.model_validate(task.request)
        retry_task = self.create(request)
        return self.update(
            retry_task.task_id,
            message=f"由任务 {task_id} 重试创建",
            log=f"由任务 {task_id} 重试创建",
        )

    def is_cancel_requested(self, task_id: str) -> bool:
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        return any("请求取消" in item for item in task.logs)

    def mark_canceled(self, task_id: str, message: str = "部署包任务已取消") -> PackageTask:
        return self.update(
            task_id,
            status="canceled",
            progress=100,
            message=message,
            error="",
            log=message,
        )

    def update(
        self,
        task_id: str,
        *,
        status: TaskStatus | None = None,
        progress: int | None = None,
        message: str | None = None,
        result: PackageBuildResult | None = None,
        error: str | None = None,
        log: str | None = None,
    ) -> PackageTask:
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        logs = [*task.logs]
        if log:
            logs.append(log)
        updated = task.model_copy(
            update={
                "status": status or task.status,
                "progress": task.progress if progress is None else max(0, min(100, progress)),
                "message": task.message if message is None else message,
                "result": task.result if result is None else result,
                "error": task.error if error is None else error,
                "logs": logs,
                "updated_at": _now_iso(),
            }
        )
        with self._connect() as conn:
            row = conn.execute(
                """
                update package_tasks
                set status = %s, progress = %s, message = %s, request_json = %s,
                    result_json = %s, error = %s, logs_json = %s,
                    worker_id = %s, claimed_at = %s, heartbeat_at = %s,
                    created_at = %s, updated_at = %s
                where task_id = %s
                returning *
                """,
                (*_task_to_row(updated)[1:], updated.task_id),
            ).fetchone()
        if row is None:
            raise KeyError(task_id)
        return _task_from_row(row)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists package_tasks (
                    task_id text primary key,
                    status text not null,
                    progress integer not null,
                    message text not null,
                    request_json text not null,
                    result_json text,
                    error text not null,
                    logs_json text not null,
                    worker_id text not null default '',
                    claimed_at text not null default '',
                    heartbeat_at text not null default '',
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute("create index if not exists idx_package_tasks_status_created_at on package_tasks(status, created_at)")
            conn.execute("create index if not exists idx_package_tasks_updated_at on package_tasks(updated_at)")

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            yield conn


class PostgresAuditEventRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
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
        def insert_event() -> None:
            with self._connect() as conn:
                conn.execute(
                    """
                    insert into audit_events(
                        event_id, action, target_id, status, operator, client_ip,
                        message, metadata_json, created_at
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    _event_to_row(event),
                )

        self._with_schema_retry(insert_event)
        return event

    def list(self, limit: int = 100) -> list[AuditEvent]:
        def fetch_rows() -> list[dict]:
            with self._connect() as conn:
                return conn.execute(
                    "select * from audit_events order by created_at desc limit %s",
                    (max(1, min(500, limit)),),
                ).fetchall()

        rows = self._with_schema_retry(fetch_rows)
        return [_event_from_row(row) for row in rows]

    def metrics_summary(self) -> dict:
        def fetch_summary() -> tuple[int, list[dict]]:
            with self._connect() as conn:
                total = conn.execute("select count(*) as count from audit_events").fetchone()["count"]
                action_rows = conn.execute(
                    "select action, count(*) as count from audit_events group by action"
                ).fetchall()
            return total, action_rows

        total, action_rows = self._with_schema_retry(fetch_summary)
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

    def _with_schema_retry(self, operation: Callable[[], T]) -> T:
        try:
            return operation()
        except psycopg.errors.UndefinedTable:
            self._ensure_schema()
            return operation()

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            yield conn


def _task_to_row(task: PackageTask) -> tuple:
    return (
        task.task_id,
        task.status,
        task.progress,
        task.message,
        json.dumps(task.request, ensure_ascii=False),
        task.result.model_dump_json(by_alias=True) if task.result else None,
        task.error,
        json.dumps(task.logs, ensure_ascii=False),
        task.worker_id,
        task.claimed_at,
        task.heartbeat_at,
        task.created_at,
        task.updated_at,
    )


def _task_from_row(row: dict) -> PackageTask:
    result_raw = row["result_json"]
    return PackageTask(
        taskId=row["task_id"],
        status=row["status"],
        progress=row["progress"],
        message=row["message"],
        request=json.loads(row["request_json"]),
        result=PackageBuildResult.model_validate_json(result_raw) if result_raw else None,
        artifactAvailable=_artifact_available(result_raw),
        error=row["error"],
        logs=json.loads(row["logs_json"]),
        workerId=row["worker_id"],
        claimedAt=row["claimed_at"],
        heartbeatAt=row["heartbeat_at"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


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


def _event_from_row(row: dict) -> AuditEvent:
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
