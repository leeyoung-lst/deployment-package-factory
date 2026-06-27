from __future__ import annotations

from fastapi.testclient import TestClient

from deployment_package_factory.api import deployment_packages
from deployment_package_factory.main import create_app
from deployment_package_factory.services.deployment_packages.audit_repository import AuditEventRepository
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository


def test_metrics_endpoint_exports_prometheus_text(tmp_path, monkeypatch) -> None:
    task_repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    audit_repo = AuditEventRepository(tmp_path / "audit.sqlite3")
    task_repo.create(PackageBuildRequest())
    audit_repo.record(action="package.create", status="accepted")
    monkeypatch.setattr(deployment_packages, "_TASK_REPO", task_repo)
    monkeypatch.setattr(deployment_packages, "_AUDIT_REPO", audit_repo)

    response = TestClient(create_app()).get("/metrics")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/plain")
    assert "deployment_package_tasks_total 1" in response.text
    assert 'deployment_package_audit_events_by_action{action="package.create"} 1' in response.text
