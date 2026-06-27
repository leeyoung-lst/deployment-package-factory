from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from deployment_package_factory.services.deployment_packages.models import (
    PackageBuildRequest,
    PackageBuildResult,
    PackageTask,
    TaskStatus,
)


DEFAULT_TASK_DB = Path(__file__).resolve().parents[4] / "data" / "deployment-package-tasks.sqlite3"


class PackageTaskRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_TASK_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _task_to_row(task),
            )
        return task

    def get(self, task_id: str) -> PackageTask | None:
        with self._connect() as conn:
            row = conn.execute("select * from package_tasks where task_id = ?", (task_id,)).fetchone()
        return _task_from_row(row) if row else None

    def list(self, limit: int = 50) -> list[PackageTask]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from package_tasks order by created_at desc limit ?",
                (limit,),
            ).fetchall()
        return [_task_from_row(row) for row in rows]

    def claim_next_pending(self, worker_id: str = "") -> PackageTask | None:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute("begin immediate")
            row = conn.execute(
                """
                select * from package_tasks
                where status = 'pending'
                order by created_at asc
                limit 1
                """
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            logs = [*json.loads(row["logs_json"]), "Worker 已领取任务"]
            conn.execute(
                """
                update package_tasks
                set status = ?, progress = ?, message = ?, logs_json = ?,
                    worker_id = ?, claimed_at = ?, heartbeat_at = ?, updated_at = ?
                where task_id = ?
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
            )
            claimed = conn.execute("select * from package_tasks where task_id = ?", (row["task_id"],)).fetchone()
            conn.commit()
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
            conn.execute(
                """
                update package_tasks
                set heartbeat_at = ?, updated_at = ?
                where task_id = ? and status = 'running'
                """,
                (now, now, task_id),
            )
            row = conn.execute("select * from package_tasks where task_id = ?", (task_id,)).fetchone()
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
                conn.execute(
                    """
                    update package_tasks
                    set status = ?, progress = ?, message = ?, error = ?, logs_json = ?, updated_at = ?
                    where task_id = ?
                    """,
                    ("failed", 100, "部署包生成失败", error, json.dumps(logs, ensure_ascii=False), now, row["task_id"]),
                )
                updated_row = conn.execute("select * from package_tasks where task_id = ?", (row["task_id"],)).fetchone()
                if updated_row:
                    updated.append(_task_from_row(updated_row))
        return updated

    def mark_running(self, task_id: str, message: str = "正在生成部署包", worker_id: str = "") -> PackageTask:
        task = self.update(task_id, status="running", progress=10, message=message, log=message)
        if task.worker_id or not worker_id:
            return task
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                update package_tasks
                set worker_id = ?, claimed_at = ?, heartbeat_at = ?, updated_at = ?
                where task_id = ?
                """,
                (worker_id, now, now, now, task_id),
            )
            row = conn.execute("select * from package_tasks where task_id = ?", (task_id,)).fetchone()
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
            conn.execute(
                """
                update package_tasks
                set status = ?, progress = ?, message = ?, request_json = ?,
                    result_json = ?, error = ?, logs_json = ?,
                    worker_id = ?, claimed_at = ?, heartbeat_at = ?,
                    created_at = ?, updated_at = ?
                where task_id = ?
                """,
                (*_task_to_row(updated)[1:], updated.task_id),
            )
        return updated

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
            existing_columns = {
                row["name"]
                for row in conn.execute("pragma table_info(package_tasks)").fetchall()
            }
            for column_name in ("worker_id", "claimed_at", "heartbeat_at"):
                if column_name not in existing_columns:
                    conn.execute(f"alter table package_tasks add column {column_name} text not null default ''")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


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


def _task_from_row(row: sqlite3.Row) -> PackageTask:
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


def _artifact_available(result_raw: str | None) -> bool:
    if not result_raw:
        return False
    result = PackageBuildResult.model_validate_json(result_raw)
    return Path(result.artifact_path).is_file()


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
