from __future__ import annotations

import asyncio

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
