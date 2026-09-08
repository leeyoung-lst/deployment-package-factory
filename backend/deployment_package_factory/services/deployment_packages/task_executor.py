from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from deployment_package_factory.services.deployment_packages.builder import PackageBuildError, build_deployment_package
from deployment_package_factory.services.deployment_packages.catalog import CatalogError
from deployment_package_factory.services.deployment_packages.error_diagnosis import diagnose_error
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
            self._finish_error(task_id, exc, context={"operation": "build_package", "payload": payload.model_dump(by_alias=True)})
        except Exception as exc:  # pragma: no cover - defensive boundary for background execution
            self._finish_error(task_id, exc, context={"operation": "build_package", "payload": payload.model_dump(by_alias=True)})

    def _finish_error(self, task_id: str, error: Exception | str, context: dict | None = None) -> PackageTask:
        if self.repo.is_cancel_requested(task_id):
            return self.repo.mark_canceled(task_id)

        # 如果是字符串，直接使用（向后兼容）
        if isinstance(error, str):
            return self.repo.mark_failed(task_id, error)

        # 使用智能错误诊断
        diagnosis = diagnose_error(error, context)

        # 构建用户友好的错误消息
        error_message = diagnosis.user_message
        if diagnosis.possible_causes:
            error_message += f"\n\n可能原因：\n" + "\n".join(f"• {cause}" for cause in diagnosis.possible_causes[:3])
        if diagnosis.solutions:
            error_message += f"\n\n解决方案：\n" + "\n".join(f"{i+1}. {sol}" for i, sol in enumerate(diagnosis.solutions[:3]))

        # 添加技术细节（可选查看）
        error_message += f"\n\n技术细节：{diagnosis.technical_details}"

        return self.repo.mark_failed(task_id, error_message)

    async def _build_with_heartbeat(self, task_id: str, payload: PackageBuildRequest):
        stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(task_id, stop))

        def progress_callback(progress: int, message: str) -> None:
            """进度回调函数，从构建线程更新任务进度"""
            try:
                self.repo.update_progress(task_id, progress, message)
            except Exception:
                pass  # 进度更新失败不影响构建

        try:
            return await asyncio.to_thread(
                build_deployment_package,
                payload,
                output_dir=self.config.output_dir,
                progress_callback=progress_callback
            )
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
