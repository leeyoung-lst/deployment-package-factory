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


def test_task_repository_metrics_summary_counts_status_and_artifacts(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    artifact = tmp_path / "pkg.tar.gz"
    artifact.write_bytes(b"package")
    completed = repo.create(PackageBuildRequest())
    failed = repo.create(PackageBuildRequest())
    repo.mark_completed(
        completed.task_id,
        PackageBuildResult(
            packageId="pkg-1",
            workDir=str(tmp_path / "work"),
            artifactPath=str(artifact),
            sha256="abc",
            manifest={},
        ),
    )
    repo.mark_failed(failed.task_id, "failed")

    summary = repo.metrics_summary()

    assert summary["total"] == 2
    assert summary["byStatus"]["completed"] == 1
    assert summary["byStatus"]["failed"] == 1
    assert summary["availableArtifacts"] == 1
    assert summary["artifactBytes"] == len(b"package")


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

    claimed = repo.claim_next_pending("worker-a")

    assert claimed is not None
    assert claimed.task_id == first.task_id
    assert claimed.status == "running"
    assert claimed.worker_id == "worker-a"
    assert claimed.claimed_at
    assert claimed.heartbeat_at
    assert "Worker 已领取任务" in claimed.logs
    remaining = repo.get(second.task_id)
    assert remaining is not None
    assert remaining.status == "pending"


def test_task_repository_heartbeat_refreshes_owned_running_task(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="eam")]))
    claimed = repo.claim_next_pending("worker-a")
    assert claimed is not None
    stale_at = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "update package_tasks set heartbeat_at = ?, updated_at = ? where task_id = ?",
            (stale_at, stale_at, task.task_id),
        )

    refreshed = repo.heartbeat(task.task_id, "worker-a")

    assert refreshed.worker_id == "worker-a"
    assert datetime.fromisoformat(refreshed.heartbeat_at) > datetime.fromisoformat(stale_at)


def test_task_repository_rejects_heartbeat_from_another_worker(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="eam")]))
    claimed = repo.claim_next_pending("worker-a")
    assert claimed is not None

    try:
        repo.heartbeat(claimed.task_id, "worker-b")
    except ValueError as exc:
        assert "worker-a" in str(exc)
    else:
        raise AssertionError("Expected heartbeat from a different worker to fail")


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


def test_task_repository_stale_detection_uses_heartbeat(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="eam")]))
    repo.claim_next_pending("worker-a")
    stale_at = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    fresh_at = datetime.now(timezone.utc).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "update package_tasks set heartbeat_at = ?, updated_at = ? where task_id = ?",
            (fresh_at, stale_at, task.task_id),
        )

    updated = repo.mark_stale_running_failed(timeout_minutes=30)

    assert updated == []
    reloaded = repo.get(task.task_id)
    assert reloaded is not None
    assert reloaded.status == "running"


def test_task_repository_migrates_worker_lease_columns(tmp_path) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    with PackageTaskRepository(db_path)._connect() as conn:
        conn.execute("alter table package_tasks rename to package_tasks_new")
        conn.execute(
            """
            create table package_tasks (
                task_id text primary key,
                status text not null,
                progress integer not null,
                message text not null,
                request_json text not null,
                result_json text,
                error text not null,
                logs_json text not null,
                created_at text not null,
                updated_at text not null
            )
            """
        )
        conn.execute("drop table package_tasks_new")

    repo = PackageTaskRepository(db_path)
    task = repo.create(PackageBuildRequest())
    claimed = repo.claim_next_pending("worker-a")

    assert task.worker_id == ""
    assert claimed is not None
    assert claimed.worker_id == "worker-a"
