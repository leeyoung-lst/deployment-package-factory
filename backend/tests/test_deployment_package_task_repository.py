from __future__ import annotations

from deployment_package_factory.services.deployment_packages.models import (
    BusinessSelection,
    PackageBuildRequest,
    PackageBuildResult,
)
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository


def test_task_repository_persists_lifecycle(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    request = PackageBuildRequest(
        sourceEnv="test",
        deployModes=["k8s"],
        businessServices=[BusinessSelection(name="eam")],
        database="postgres",
    )

    created = repo.create(request)
    running = repo.mark_running(created.task_id)
    completed = repo.mark_completed(
        created.task_id,
        PackageBuildResult(
            packageId="pkg-1",
            workDir="/tmp/work",
            artifactPath="/tmp/pkg.tar.gz",
            sha256="abc",
            manifest={"database": "postgres"},
        ),
    )

    reloaded = PackageTaskRepository(tmp_path / "tasks.sqlite3").get(created.task_id)

    assert created.status == "pending"
    assert running.status == "running"
    assert completed.status == "completed"
    assert completed.progress == 100
    assert completed.result is not None
    assert reloaded is not None
    assert reloaded.result is not None
    assert reloaded.result.package_id == "pkg-1"
    assert "部署包生成完成" in reloaded.logs


def test_task_repository_records_failure(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="mes")]))

    failed = repo.mark_failed(task.task_id, "Docker CLI is not available.")

    assert failed.status == "failed"
    assert failed.error == "Docker CLI is not available."
    assert failed.progress == 100
    assert any("Docker CLI" in item for item in failed.logs)
