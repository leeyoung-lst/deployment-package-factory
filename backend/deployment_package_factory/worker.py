from __future__ import annotations

import argparse
import asyncio
import logging

from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest
from deployment_package_factory.services.deployment_packages.task_executor import PackageTaskExecutor, PackageTaskExecutorConfig
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository


LOGGER = logging.getLogger("deployment_package_factory.worker")


async def run_worker(*, once: bool = False) -> None:
    settings = load_settings()
    repo = PackageTaskRepository(settings.task_db_path)
    executor = PackageTaskExecutor(
        repo,
        PackageTaskExecutorConfig(max_concurrent_builds=settings.max_concurrent_builds, output_dir=settings.output_dir),
    )
    LOGGER.info("Deployment package worker started with poll interval %ss", settings.worker_poll_interval_seconds)
    while True:
        stale_tasks = repo.mark_stale_running_failed(settings.running_task_timeout_minutes)
        for stale_task in stale_tasks:
            LOGGER.warning("Marked stale deployment package task %s as failed", stale_task.task_id)
        task = repo.claim_next_pending()
        if task is None:
            if once:
                return
            await asyncio.sleep(settings.worker_poll_interval_seconds)
            continue
        LOGGER.info("Running deployment package task %s", task.task_id)
        await executor.run(task.task_id, PackageBuildRequest.model_validate(task.request))
        if once:
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Deployment package factory worker")
    parser.add_argument("--once", action="store_true", help="Run at most one pending task and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run_worker(once=args.once))


if __name__ == "__main__":
    main()
