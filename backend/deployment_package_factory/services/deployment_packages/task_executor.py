from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from deployment_package_factory.services.deployment_packages.builder import PackageBuildError, build_deployment_package
from deployment_package_factory.services.deployment_packages.catalog import CatalogError
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest, PackageTask
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository


@dataclass(frozen=True)
class PackageTaskExecutorConfig:
    max_concurrent_builds: int = 1
    output_dir: Path | None = None


class PackageTaskExecutor:
    def __init__(self, repo: PackageTaskRepository, config: PackageTaskExecutorConfig | None = None) -> None:
        self.repo = repo
        self.config = config or PackageTaskExecutorConfig()
        self._semaphore = asyncio.Semaphore(max(1, self.config.max_concurrent_builds))

    async def run(self, task_id: str, payload: PackageBuildRequest) -> None:
        try:
            task = self.repo.get(task_id)
            if task is None or task.status == "canceled":
                return
            self.repo.update(task_id, status="pending", progress=5, message="等待导包执行槽位", log="等待导包执行槽位")
            async with self._semaphore:
                task = self.repo.get(task_id)
                if task is None or task.status == "canceled":
                    return
                self.repo.mark_running(task_id)
                result = await asyncio.to_thread(build_deployment_package, payload, output_dir=self.config.output_dir)
                if self.repo.is_cancel_requested(task_id):
                    self.repo.mark_canceled(task_id, "部署包任务已取消，已丢弃本次构建结果")
                else:
                    self.repo.mark_completed(task_id, result)
        except (CatalogError, PackageBuildError) as exc:
            self._finish_error(task_id, str(exc))
        except Exception as exc:  # pragma: no cover - defensive boundary for background execution
            self._finish_error(task_id, f"Unexpected deployment package error: {exc}")

    def _finish_error(self, task_id: str, error: str) -> PackageTask:
        if self.repo.is_cancel_requested(task_id):
            return self.repo.mark_canceled(task_id)
        return self.repo.mark_failed(task_id, error)
