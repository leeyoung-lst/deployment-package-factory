from __future__ import annotations

from deployment_package_factory.metrics import render_metrics
from deployment_package_factory.services.deployment_packages.audit_repository import AuditEventRepository
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository


def test_render_metrics_exports_task_and_audit_series(tmp_path) -> None:
    task_repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    audit_repo = AuditEventRepository(tmp_path / "audit.sqlite3")
    task = task_repo.create(PackageBuildRequest())
    task_repo.mark_failed(task.task_id, "failed")
    audit_repo.record(action='package."create"', status="accepted")

    payload = render_metrics(task_repo, audit_repo)

    assert "deployment_package_tasks_total 1" in payload
    assert 'deployment_package_tasks_by_status{status="failed"} 1' in payload
    assert "deployment_package_artifacts_available 0" in payload
    assert "deployment_package_audit_events_total 1" in payload
    assert 'deployment_package_audit_events_by_action{action="package.\\"create\\""} 1' in payload
