from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
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
                    error, logs_json, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def mark_running(self, task_id: str, message: str = "正在生成部署包") -> PackageTask:
        return self.update(task_id, status="running", progress=10, message=message, log=message)

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
                    result_json = ?, error = ?, logs_json = ?, created_at = ?, updated_at = ?
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
                    created_at text not null,
                    updated_at text not null
                )
                """
            )

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
        error=row["error"],
        logs=json.loads(row["logs_json"]),
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
