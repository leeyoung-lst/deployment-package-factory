from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from deployment_package_factory import worker
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest, PackageBuildResult
from fakes import InMemoryTaskRepository


def test_worker_runs_one_pending_task(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "packages"
    repo = InMemoryTaskRepository()
    task = repo.create(PackageBuildRequest())
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_WORKER_ID", "worker-test")
    monkeypatch.setattr(worker, "create_task_repository", lambda database_url="": repo)
    monkeypatch.setattr(
        "deployment_package_factory.services.deployment_packages.task_executor.build_deployment_package",
        lambda payload, *, output_dir=None: PackageBuildResult(
            packageId="pkg-worker",
            workDir=str(tmp_path / "work"),
            artifactPath=str(tmp_path / "pkg.tar.gz"),
            sha256="abc",
            manifest={},
        ),
    )

    asyncio.run(worker.run_worker(once=True))

    completed = repo.get(task.task_id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.worker_id == "worker-test"
    assert completed.heartbeat_at
    assert completed.result is not None
    assert completed.result.package_id == "pkg-worker"


def test_worker_marks_stale_running_task_failed(tmp_path, monkeypatch) -> None:
    repo = InMemoryTaskRepository()
    task = repo.create(PackageBuildRequest())
    repo.mark_running(task.task_id)
    stale_at = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    repo.set_updated_at(task.task_id, stale_at)
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_RUNNING_TASK_TIMEOUT_MINUTES", "30")
    monkeypatch.setattr(worker, "create_task_repository", lambda database_url="": repo)

    asyncio.run(worker.run_worker(once=True))

    failed = repo.get(task.task_id)
    assert failed is not None
    assert failed.status == "failed"
    assert "timed out" in failed.error
