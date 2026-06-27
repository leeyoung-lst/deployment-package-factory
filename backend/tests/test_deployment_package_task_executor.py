from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest, PackageBuildResult
from deployment_package_factory.services.deployment_packages.task_executor import PackageTaskExecutor, PackageTaskExecutorConfig
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository


def test_task_executor_uses_configured_output_dir(tmp_path, monkeypatch) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = repo.create(PackageBuildRequest())
    seen = {}

    def fake_build(payload, *, output_dir=None):
        seen["output_dir"] = output_dir
        return PackageBuildResult(
            packageId="pkg-1",
            workDir="/tmp/work",
            artifactPath="/tmp/pkg.tar.gz",
            sha256="abc",
            manifest={},
        )

    monkeypatch.setattr(
        "deployment_package_factory.services.deployment_packages.task_executor.build_deployment_package",
        fake_build,
    )

    executor = PackageTaskExecutor(repo, PackageTaskExecutorConfig(max_concurrent_builds=2, output_dir=tmp_path / "packages"))

    asyncio.run(executor.run(task.task_id, PackageBuildRequest()))

    completed = repo.get(task.task_id)
    assert completed is not None
    assert completed.status == "completed"
    assert seen["output_dir"] == tmp_path / "packages"


def test_task_executor_discards_result_after_cancel_request(tmp_path, monkeypatch) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = repo.create(PackageBuildRequest())
    repo.mark_running(task.task_id)
    repo.cancel(task.task_id)

    monkeypatch.setattr(
        "deployment_package_factory.services.deployment_packages.task_executor.build_deployment_package",
        lambda payload, *, output_dir=None: PackageBuildResult(
            packageId="pkg-1",
            workDir="/tmp/work",
            artifactPath="/tmp/pkg.tar.gz",
            sha256="abc",
            manifest={},
        ),
    )

    executor = PackageTaskExecutor(repo, PackageTaskExecutorConfig(output_dir=tmp_path / "packages"))

    asyncio.run(executor.run(task.task_id, PackageBuildRequest()))

    canceled = repo.get(task.task_id)
    assert canceled is not None
    assert canceled.status == "canceled"
    assert canceled.result is None


def test_task_executor_refreshes_heartbeat_while_building(tmp_path, monkeypatch) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = repo.create(PackageBuildRequest())
    stale_at = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()

    def fake_build(payload, *, output_dir=None):
        time.sleep(0.08)
        return PackageBuildResult(
            packageId="pkg-1",
            workDir="/tmp/work",
            artifactPath="/tmp/pkg.tar.gz",
            sha256="abc",
            manifest={},
        )

    monkeypatch.setattr(
        "deployment_package_factory.services.deployment_packages.task_executor.build_deployment_package",
        fake_build,
    )

    executor = PackageTaskExecutor(
        repo,
        PackageTaskExecutorConfig(output_dir=tmp_path / "packages", heartbeat_seconds=1, worker_id="worker-a"),
    )

    async def run_and_age_heartbeat() -> None:
        running = asyncio.create_task(executor.run(task.task_id, PackageBuildRequest()))
        await asyncio.sleep(0.01)
        with repo._connect() as conn:
            conn.execute(
                "update package_tasks set heartbeat_at = ?, updated_at = ? where task_id = ?",
                (stale_at, stale_at, task.task_id),
            )
        await running

    asyncio.run(run_and_age_heartbeat())

    completed = repo.get(task.task_id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.worker_id == "worker-a"
    assert datetime.fromisoformat(completed.heartbeat_at) > datetime.fromisoformat(stale_at)
