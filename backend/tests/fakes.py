from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from deployment_package_factory.services.deployment_packages.kubernetes_runtime import RegisteredBusinessPlatform
from deployment_package_factory.services.deployment_packages.models import (
    AuditEvent,
    BusinessPlatform,
    PackageBuildRequest,
    PackageBuildResult,
    PackageTask,
    TaskStatus,
)
from deployment_package_factory.services.microservices.repository import _microservice_payload
from deployment_package_factory.services.microservices.scaffold import MicroserviceScaffoldRequest, MicroserviceScaffoldResult


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self.tasks: dict[str, PackageTask] = {}

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
        self.tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> PackageTask | None:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        return task.model_copy(update={"artifact_available": _artifact_available(task.result)})

    def list(self, limit: int = 50) -> list[PackageTask]:
        tasks = sorted(self.tasks.values(), key=lambda item: item.created_at, reverse=True)
        return [item.model_copy(update={"artifact_available": _artifact_available(item.result)}) for item in tasks[:limit]]

    def metrics_summary(self) -> dict:
        by_status: dict[str, int] = {}
        artifact_bytes = 0
        available_artifacts = 0
        for task in self.tasks.values():
            by_status[task.status] = by_status.get(task.status, 0) + 1
            if task.status == "completed" and task.result and Path(task.result.artifact_path).is_file():
                available_artifacts += 1
                artifact_bytes += Path(task.result.artifact_path).stat().st_size
        return {
            "total": len(self.tasks),
            "byStatus": by_status,
            "availableArtifacts": available_artifacts,
            "artifactBytes": artifact_bytes,
        }

    def claim_next_pending(self, worker_id: str = "") -> PackageTask | None:
        pending = [task for task in self.tasks.values() if task.status == "pending"]
        if not pending:
            return None
        task = sorted(pending, key=lambda item: item.created_at)[0]
        now = _now_iso()
        return self._store(
            task.model_copy(
                update={
                    "status": "running",
                    "progress": 8,
                    "message": "Worker 已领取任务，等待执行",
                    "logs": [*task.logs, "Worker 已领取任务"],
                    "worker_id": worker_id,
                    "claimed_at": now,
                    "heartbeat_at": now,
                    "updated_at": now,
                }
            )
        )

    def heartbeat(self, task_id: str, worker_id: str = "") -> PackageTask:
        task = self._require(task_id)
        if task.status != "running":
            return task
        if task.worker_id and worker_id and task.worker_id != worker_id:
            raise ValueError(f"Task {task_id} is owned by worker {task.worker_id}.")
        now = _now_iso()
        return self._store(task.model_copy(update={"heartbeat_at": now, "updated_at": now}))

    def mark_stale_running_failed(self, timeout_minutes: int) -> list[PackageTask]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, timeout_minutes))
        updated: list[PackageTask] = []
        for task in list(self.tasks.values()):
            if task.status != "running":
                continue
            if _parse_iso(task.heartbeat_at or task.updated_at) >= cutoff:
                continue
            error = f"Worker task timed out after {timeout_minutes} minutes."
            updated.append(
                self.update(
                    task.task_id,
                    status="failed",
                    progress=100,
                    message="部署包生成失败",
                    error=error,
                    log=f"部署包生成失败：{error}",
                )
            )
        return updated

    def mark_running(self, task_id: str, message: str = "正在生成部署包", worker_id: str = "") -> PackageTask:
        task = self.update(task_id, status="running", progress=10, message=message, log=message)
        if worker_id and not task.worker_id:
            now = _now_iso()
            task = self._store(task.model_copy(update={"worker_id": worker_id, "claimed_at": now, "heartbeat_at": now, "updated_at": now}))
        return task

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
        task = self._require(task_id)
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
        return self.update(task_id, message="部署包任务已请求取消，等待当前步骤结束", log="部署包任务已请求取消")

    def retry(self, task_id: str) -> PackageTask:
        task = self._require(task_id)
        if task.status not in {"failed", "canceled"}:
            raise ValueError(f"Task {task_id} cannot be retried from status {task.status}.")
        retry_task = self.create(PackageBuildRequest.model_validate(task.request).with_image_archive())
        return self.update(retry_task.task_id, message=f"由任务 {task_id} 重试创建", log=f"由任务 {task_id} 重试创建")

    def is_cancel_requested(self, task_id: str) -> bool:
        return any("请求取消" in item for item in self._require(task_id).logs)

    def mark_canceled(self, task_id: str, message: str = "部署包任务已取消") -> PackageTask:
        return self.update(task_id, status="canceled", progress=100, message=message, error="", log=message)

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
        task = self._require(task_id)
        logs = [*task.logs]
        if log:
            logs.append(log)
        return self._store(
            task.model_copy(
                update={
                    "status": status or task.status,
                    "progress": task.progress if progress is None else max(0, min(100, progress)),
                    "message": task.message if message is None else message,
                    "result": task.result if result is None else result,
                    "artifact_available": _artifact_available(task.result if result is None else result),
                    "error": task.error if error is None else error,
                    "logs": logs,
                    "updated_at": _now_iso(),
                }
            )
        )

    def set_created_at(self, task_id: str, value: str) -> PackageTask:
        task = self._require(task_id)
        return self._store(task.model_copy(update={"created_at": value, "updated_at": value}))

    def set_updated_at(self, task_id: str, value: str) -> PackageTask:
        task = self._require(task_id)
        return self._store(task.model_copy(update={"updated_at": value}))

    def set_heartbeat_at(self, task_id: str, heartbeat_at: str, updated_at: str | None = None) -> PackageTask:
        task = self._require(task_id)
        return self._store(task.model_copy(update={"heartbeat_at": heartbeat_at, "updated_at": updated_at or task.updated_at}))

    def _require(self, task_id: str) -> PackageTask:
        task = self.tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        return task

    def _store(self, task: PackageTask) -> PackageTask:
        self.tasks[task.task_id] = task
        return task


class InMemoryAuditEventRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

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
        event = AuditEvent(
            eventId=f"audit-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            action=action,
            targetId=target_id,
            status=status,
            operator=operator,
            clientIp=client_ip,
            message=message,
            metadata=metadata or {},
            createdAt=_now_iso(),
        )
        self.events.append(event)
        return event

    def list(
        self,
        limit: int = 100,
        *,
        status: str = "",
        action: str = "",
        action_prefix: str = "",
    ) -> list[AuditEvent]:
        events = list(reversed(self.events))
        if status:
            events = [event for event in events if event.status == status]
        if action:
            events = [event for event in events if event.action == action]
        if action_prefix:
            events = [event for event in events if event.action.startswith(action_prefix)]
        return events[: max(1, min(500, limit))]

    def metrics_summary(self) -> dict:
        by_action: dict[str, int] = {}
        for event in self.events:
            by_action[event.action] = by_action.get(event.action, 0) + 1
        return {"total": len(self.events), "byAction": by_action}


class InMemoryBusinessPlatformRepository:
    def __init__(self) -> None:
        self.platforms: dict[tuple[str, str, str], BusinessPlatform] = {}

    def upsert_registered(self, item: RegisteredBusinessPlatform, metadata: dict | None = None) -> BusinessPlatform:
        key = (item.source_env, item.key, item.profile or "")
        existing = self.platforms.get(key)
        now = _now_iso()
        platform = BusinessPlatform(
            key=item.key,
            name=item.name,
            profile=item.profile or "",
            namespace=item.namespace,
            sourceEnv=item.source_env,
            status=item.status,
            metadata=metadata or (existing.metadata if existing else {}),
            createdAt=existing.created_at if existing else now,
            updatedAt=now,
        )
        self.platforms[key] = platform
        return platform

    def get(self, source_env: str, key: str, profile: str = "") -> BusinessPlatform | None:
        return self.platforms.get((source_env, key, profile or ""))

    def resolve(self, source_env: str, key: str, profile: str = "") -> BusinessPlatform:
        if profile:
            platform = self.get(source_env, key, profile)
            if platform is None:
                raise KeyError(f"{source_env}/{key}/{profile}")
            return platform
        matches = [item for item in self.list(source_env, include_disabled=True) if item.key == key]
        if not matches:
            raise KeyError(f"{source_env}/{key}")
        if len(matches) > 1:
            profiles = ", ".join(item.profile or "<default>" for item in matches)
            raise ValueError(f"Business platform {source_env}/{key} has multiple profiles: {profiles}.")
        return matches[0]

    def list(self, source_env: str | None = None, *, include_disabled: bool = False) -> list[BusinessPlatform]:
        items = list(self.platforms.values())
        if source_env:
            items = [item for item in items if item.source_env == source_env]
        if not include_disabled:
            items = [item for item in items if item.status != "disabled"]
        return sorted(items, key=lambda item: (item.source_env, item.key, item.profile, item.namespace))

    def disable(self, source_env: str, key: str, profile: str = "") -> BusinessPlatform:
        platform = self.resolve(source_env, key, profile)
        updated = platform.model_copy(update={"status": "disabled", "updated_at": _now_iso()})
        self.platforms[(updated.source_env, updated.key, updated.profile)] = updated
        return updated


class InMemoryMicroserviceRepository:
    def __init__(self) -> None:
        self.services: dict[tuple[str, str, str, str], dict] = {}

    def upsert(self, request: MicroserviceScaffoldRequest, result: MicroserviceScaffoldResult) -> dict:
        key = (request.source_env, request.business_platform_key, request.business_platform_profile or "", request.service_key)
        existing = self.services.get(key)
        now = _now_iso()
        row = _microservice_payload(request, result, existing["createdAt"] if existing else now, now)
        self.services[key] = row
        return row

    def get(self, source_env: str, business_platform_key: str, business_platform_profile: str, service_key: str) -> dict | None:
        return self.services.get((source_env, business_platform_key, business_platform_profile or "", service_key))

    def get_by_project_id(self, project_id: str) -> dict | None:
        return next((row for row in self.services.values() if row["projectId"] == project_id), None)

    def update_delivery(self, project_id: str, delivery: dict[str, object]) -> dict | None:
        row = self.get_by_project_id(project_id)
        if not row:
            return None
        row["delivery"] = delivery
        row["updatedAt"] = _now_iso()
        return row

    def update_fields(self, project_id: str, fields: dict[str, object]) -> dict | None:
        row = self.get_by_project_id(project_id)
        if not row:
            return None
        row.update(fields)
        row["updatedAt"] = _now_iso()
        return row

    def list(
        self,
        *,
        source_env: str | None = None,
        business_platform_key: str | None = None,
        business_platform_profile: str | None = None,
    ) -> list[dict]:
        rows = list(self.services.values())
        if source_env:
            rows = [row for row in rows if row["sourceEnv"] == source_env]
        if business_platform_key:
            rows = [row for row in rows if row["businessPlatformKey"] == business_platform_key]
        if business_platform_profile is not None:
            rows = [row for row in rows if row["businessPlatformProfile"] == business_platform_profile]
        return sorted(rows, key=lambda row: (row["sourceEnv"], row["businessPlatformKey"], row["businessPlatformProfile"], row["serviceKey"]))


def _artifact_available(result: PackageBuildResult | None) -> bool:
    return bool(result and Path(result.artifact_path).is_file())


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
