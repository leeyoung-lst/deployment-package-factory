from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from deployment_package_factory.services.deployment_packages.builder import PackageBuildError, build_deployment_package
from deployment_package_factory.services.deployment_packages.catalog import CatalogError
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest, PackageTask


@dataclass(frozen=True)
class PackageTaskExecutorConfig:
    max_concurrent_builds: int = 1
    output_dir: Path | None = None
    heartbeat_seconds: int = 15
    worker_id: str = ""


class PackageTaskExecutor:
    def __init__(self, repo, config: PackageTaskExecutorConfig | None = None) -> None:
        self.repo = repo
        self.config = config or PackageTaskExecutorConfig()
        self._semaphore = asyncio.Semaphore(max(1, self.config.max_concurrent_builds))

    async def run(self, task_id: str, payload: PackageBuildRequest) -> None:
        try:
            task = self.repo.get(task_id)
            if task is None or task.status == "canceled":
                return
            if task.status == "pending":
                self.repo.update(task_id, status="pending", progress=5, message="等待导包执行槽位", log="等待导包执行槽位")
            async with self._semaphore:
                task = self.repo.get(task_id)
                if task is None or task.status == "canceled":
                    return
                self.repo.mark_running(task_id, worker_id=self.config.worker_id)
                result = await self._build_with_heartbeat(task_id, payload)
                # NOTE: 取消检查在构建完成后进行。若取消请求在构建过程中到达，
                # 构建结果会被丢弃（CPU/存储资源已消耗），这是当前设计的已知取舍。
                # 对于重型构建任务，可考虑引入可中断的构建流水线以减少资源浪费。
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

    async def _build_with_heartbeat(self, task_id: str, payload: PackageBuildRequest):
        stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(task_id, stop))
        try:
            return await asyncio.to_thread(build_deployment_package, payload, output_dir=self.config.output_dir)
        finally:
            try:
                self.repo.heartbeat(task_id, self.config.worker_id)
            except (KeyError, ValueError):
                pass
            stop.set()
            await heartbeat_task

    async def _heartbeat_loop(self, task_id: str, stop: asyncio.Event) -> None:
        interval = max(1, self.config.heartbeat_seconds)
        while not stop.is_set():
            try:
                self.repo.heartbeat(task_id, self.config.worker_id)
            except (KeyError, ValueError):
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TimeoutError:
                continue
