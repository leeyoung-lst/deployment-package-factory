from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from deployment_package_factory.services.deployment_packages.models import PackageTask
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository


@dataclass(frozen=True)
class CleanupPolicy:
    retention_days: int = 30
    max_total_bytes: int = 500 * 1024 * 1024 * 1024
    dry_run: bool = False


class CleanupResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scanned_tasks: int = Field(default=0, alias="scannedTasks")
    deleted_artifacts: int = Field(default=0, alias="deletedArtifacts")
    deleted_work_dirs: int = Field(default=0, alias="deletedWorkDirs")
    freed_bytes: int = Field(default=0, alias="freedBytes")
    retained_bytes: int = Field(default=0, alias="retainedBytes")
    dry_run: bool = Field(default=False, alias="dryRun")
    deleted_paths: list[str] = Field(default_factory=list, alias="deletedPaths")


def cleanup_deployment_packages(repo: PackageTaskRepository, policy: CleanupPolicy) -> CleanupResult:
    result = CleanupResult(dry_run=policy.dry_run)
    candidates = _cleanup_candidates(repo)
    result.scanned_tasks = len(candidates)
    expired_task_ids = {
        task.task_id
        for task in candidates
        if _created_at(task) < datetime.now(timezone.utc) - timedelta(days=max(1, policy.retention_days))
    }
    selected = [item for item in candidates if item.task_id in expired_task_ids]

    remaining = [item for item in candidates if item.task_id not in expired_task_ids]
    retained_bytes = sum(_task_size(item) for item in remaining)
    if retained_bytes > policy.max_total_bytes:
        for task in sorted(remaining, key=_created_at):
            if retained_bytes <= policy.max_total_bytes:
                break
            selected.append(task)
            retained_bytes -= _task_size(task)

    selected_ids = {item.task_id for item in selected}
    for task in candidates:
        if task.task_id in selected_ids:
            _delete_task_outputs(repo, task, result, dry_run=policy.dry_run)

    result.retained_bytes = sum(_task_size(item) for item in candidates if item.task_id not in selected_ids)
    return result


def _cleanup_candidates(repo: PackageTaskRepository) -> list[PackageTask]:
    return [task for task in repo.list(limit=10000) if task.status == "completed" and task.result is not None]


def _delete_task_outputs(repo: PackageTaskRepository, task: PackageTask, result: CleanupResult, *, dry_run: bool) -> None:
    if task.result is None:
        return
    artifact = Path(task.result.artifact_path)
    work_dir = Path(task.result.work_dir)
    freed = 0
    if artifact.exists() and artifact.is_file():
        freed += artifact.stat().st_size
        result.deleted_artifacts += 1
        result.deleted_paths.append(str(artifact))
        if not dry_run:
            artifact.unlink()
    if work_dir.exists() and work_dir.is_dir():
        freed += _path_size(work_dir)
        result.deleted_work_dirs += 1
        result.deleted_paths.append(str(work_dir))
        if not dry_run:
            shutil.rmtree(work_dir)
    result.freed_bytes += freed
    if freed and not dry_run:
        repo.update(task.task_id, log=f"部署包产物已清理，释放 {freed} bytes")


def _task_size(task: PackageTask) -> int:
    if task.result is None:
        return 0
    total = 0
    artifact = Path(task.result.artifact_path)
    work_dir = Path(task.result.work_dir)
    if artifact.exists() and artifact.is_file():
        total += artifact.stat().st_size
    if work_dir.exists() and work_dir.is_dir():
        total += _path_size(work_dir)
    return total


def _path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def _created_at(task: PackageTask) -> datetime:
    value = task.created_at
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
