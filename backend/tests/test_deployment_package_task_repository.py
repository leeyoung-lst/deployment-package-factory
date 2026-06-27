from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
    assert reloaded.artifact_available is False
    assert "部署包生成完成" in reloaded.logs


def test_task_repository_reports_artifact_availability(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    artifact = tmp_path / "pkg.tar.gz"
    artifact.write_bytes(b"package")
    task = repo.create(PackageBuildRequest())
    repo.mark_completed(
        task.task_id,
        PackageBuildResult(
            packageId="pkg-1",
            workDir=str(tmp_path / "work"),
            artifactPath=str(artifact),
            sha256="abc",
            manifest={},
        ),
    )

    available = repo.get(task.task_id)
    assert available is not None
    assert available.artifact_available is True

    artifact.unlink()

    unavailable = repo.get(task.task_id)
    assert unavailable is not None
    assert unavailable.artifact_available is False


def test_task_repository_records_failure(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="mes")]))

    failed = repo.mark_failed(task.task_id, "Docker CLI is not available.")

    assert failed.status == "failed"
    assert failed.error == "Docker CLI is not available."
    assert failed.progress == 100
    assert any("Docker CLI" in item for item in failed.logs)


def test_task_repository_cancels_pending_task(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="eam")]))

    canceled = repo.cancel(task.task_id)

    assert canceled.status == "canceled"
    assert canceled.progress == 100
    assert canceled.error == ""
    assert any("已取消" in item for item in canceled.logs)


def test_task_repository_marks_running_task_cancel_requested(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="eam")]))
    repo.mark_running(task.task_id)

    cancel_requested = repo.cancel(task.task_id)

    assert cancel_requested.status == "running"
    assert repo.is_cancel_requested(task.task_id) is True
    assert "请求取消" in cancel_requested.message


def test_task_repository_retries_failed_task_with_original_request(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="mes")], database="postgres"))
    repo.mark_failed(task.task_id, "failed once")

    retry = repo.retry(task.task_id)

    assert retry.task_id != task.task_id
    assert retry.status == "pending"
    assert retry.request["database"] == "postgres"
    assert retry.request["businessServices"] == [{"name": "mes", "profile": ""}]
    assert any(task.task_id in item for item in retry.logs)


def test_task_repository_claims_oldest_pending_task(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    first = repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="eam")]))
    second = repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="mes")]))

    claimed = repo.claim_next_pending()

    assert claimed is not None
    assert claimed.task_id == first.task_id
    assert claimed.status == "running"
    assert "Worker 已领取任务" in claimed.logs
    remaining = repo.get(second.task_id)
    assert remaining is not None
    assert remaining.status == "pending"


def test_task_repository_marks_stale_running_tasks_failed(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="eam")]))
    repo.mark_running(task.task_id)
    stale_at = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "update package_tasks set updated_at = ? where task_id = ?",
            (stale_at, task.task_id),
        )

    updated = repo.mark_stale_running_failed(timeout_minutes=30)

    assert len(updated) == 1
    assert updated[0].task_id == task.task_id
    assert updated[0].status == "failed"
    assert "timed out" in updated[0].error
