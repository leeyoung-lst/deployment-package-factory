from __future__ import annotations

from datetime import datetime, timedelta, timezone

from deployment_package_factory.services.deployment_packages.cleanup import CleanupPolicy, cleanup_deployment_packages
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest, PackageBuildResult
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository


def test_cleanup_deletes_expired_artifact_and_work_dir(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    task = _completed_task(repo, tmp_path, "old", age_days=40)

    result = cleanup_deployment_packages(repo, CleanupPolicy(retention_days=30, max_total_bytes=10_000))

    assert result.scanned_tasks == 1
    assert result.deleted_artifacts == 1
    assert result.deleted_work_dirs == 1
    assert result.freed_bytes > 0
    assert not (tmp_path / "artifacts" / "old.tar.gz").exists()
    assert not (tmp_path / "artifacts" / "old.tar.gz.sha256").exists()
    assert not (tmp_path / "work" / "old").exists()
    reloaded = repo.get(task.task_id)
    assert reloaded is not None
    assert any("产物已清理" in item for item in reloaded.logs)


def test_cleanup_dry_run_keeps_files(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    _completed_task(repo, tmp_path, "old", age_days=40)

    result = cleanup_deployment_packages(repo, CleanupPolicy(retention_days=30, max_total_bytes=10_000, dry_run=True))

    assert result.dry_run is True
    assert result.deleted_artifacts == 1
    assert (tmp_path / "artifacts" / "old.tar.gz").exists()
    assert (tmp_path / "work" / "old").exists()


def test_cleanup_applies_total_size_limit_to_oldest_packages(tmp_path) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    _completed_task(repo, tmp_path, "older", age_days=5, artifact_bytes=40, work_bytes=40)
    _completed_task(repo, tmp_path, "newer", age_days=1, artifact_bytes=40, work_bytes=40)

    result = cleanup_deployment_packages(repo, CleanupPolicy(retention_days=30, max_total_bytes=150))

    assert result.deleted_artifacts == 1
    assert not (tmp_path / "artifacts" / "older.tar.gz").exists()
    assert (tmp_path / "artifacts" / "newer.tar.gz").exists()


def _completed_task(
    repo: PackageTaskRepository,
    root,
    name: str,
    *,
    age_days: int,
    artifact_bytes: int = 10,
    work_bytes: int = 10,
):
    artifact = root / "artifacts" / f"{name}.tar.gz"
    work_dir = root / "work" / name
    artifact.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"a" * artifact_bytes)
    checksum = root / "artifacts" / f"{name}.tar.gz.sha256"
    checksum.write_text("abc  package.tar.gz\n", encoding="utf-8")
    (work_dir / "file.txt").write_bytes(b"b" * work_bytes)
    task = repo.create(PackageBuildRequest())
    repo.mark_completed(
        task.task_id,
        PackageBuildResult(
            packageId=f"pkg-{name}",
            workDir=str(work_dir),
            artifactPath=str(artifact),
            checksumPath=str(checksum),
            sha256="abc",
            manifest={},
        ),
    )
    created_at = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "update package_tasks set created_at = ?, updated_at = ? where task_id = ?",
            (created_at, created_at, task.task_id),
        )
    return repo.get(task.task_id)
