from __future__ import annotations

import asyncio

from deployment_package_factory import worker
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest, PackageBuildResult
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository


def test_worker_runs_one_pending_task(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "tasks.sqlite3"
    output_dir = tmp_path / "packages"
    repo = PackageTaskRepository(db_path)
    task = repo.create(PackageBuildRequest())
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_TASK_DB", str(db_path))
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_OUTPUT_DIR", str(output_dir))
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
    assert completed.result is not None
    assert completed.result.package_id == "pkg-worker"
