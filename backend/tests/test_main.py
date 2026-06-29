from __future__ import annotations

from fastapi.testclient import TestClient

from deployment_package_factory.api import deployment_packages
from deployment_package_factory.main import create_app
from deployment_package_factory.services.deployment_packages.models import ImageExportEnvironmentCheck
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest
from fakes import InMemoryAuditEventRepository, InMemoryBusinessPlatformRepository, InMemoryMicroserviceRepository, InMemoryTaskRepository


def test_metrics_endpoint_exports_prometheus_text(tmp_path, monkeypatch) -> None:
    task_repo = InMemoryTaskRepository()
    audit_repo = InMemoryAuditEventRepository()
    task_repo.create(PackageBuildRequest())
    audit_repo.record(action="package.create", status="accepted")
    monkeypatch.setattr(deployment_packages, "_TASK_REPO", task_repo)
    monkeypatch.setattr(deployment_packages, "_AUDIT_REPO", audit_repo)

    response = TestClient(create_app()).get("/metrics")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/plain")
    assert "deployment_package_tasks_total 1" in response.text
    assert 'deployment_package_audit_events_by_action{action="package.create"} 1' in response.text


def test_readiness_reports_missing_database_url(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("DEPLOYMENT_PACKAGE_DATABASE_URL", raising=False)
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_OUTPUT_DIR", str(tmp_path / "packages"))
    _set_ready_repositories(monkeypatch)

    response = TestClient(create_app()).get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert _check(payload, "database_url")["status"] == "failed"


def test_readiness_reports_ready_metadata_store(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATABASE_URL", "postgresql://factory:secret@postgres:5432/factory")
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_OUTPUT_DIR", str(tmp_path / "packages"))
    task_repo, audit_repo, business_repo, microservice_repo = _set_ready_repositories(monkeypatch)
    task_repo.create(PackageBuildRequest())
    audit_repo.record(action="package.create", status="accepted")
    monkeypatch.setattr(
        "deployment_package_factory.main.check_image_export_environment",
        lambda: ImageExportEnvironmentCheck(
            available=True,
            exportTool="skopeo",
            toolVersion="skopeo version 1.14.0",
            dockerVersion="",
            message="ready",
        ),
    )

    response = TestClient(create_app()).get("/health/ready")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ready"
    assert _check(payload, "metadata_store")["details"]["tasks"] == 1
    assert _check(payload, "metadata_store")["details"]["auditEvents"] == 1
    assert _check(payload, "output_dir")["status"] == "ok"


def test_readiness_allows_image_export_warning(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATABASE_URL", "postgresql://factory:secret@postgres:5432/factory")
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_OUTPUT_DIR", str(tmp_path / "packages"))
    _set_ready_repositories(monkeypatch)
    monkeypatch.setattr(
        "deployment_package_factory.main.check_image_export_environment",
        lambda: ImageExportEnvironmentCheck(
            available=False,
            exportTool="",
            toolVersion="",
            dockerVersion="",
            message="No image export tool is available.",
        ),
    )

    response = TestClient(create_app()).get("/health/ready")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "degraded"
    assert _check(response.json(), "image_export")["status"] == "warning"


def _set_ready_repositories(monkeypatch):
    task_repo = InMemoryTaskRepository()
    audit_repo = InMemoryAuditEventRepository()
    business_repo = InMemoryBusinessPlatformRepository()
    microservice_repo = InMemoryMicroserviceRepository()
    monkeypatch.setattr(deployment_packages, "_TASK_REPO", task_repo)
    monkeypatch.setattr(deployment_packages, "_AUDIT_REPO", audit_repo)
    monkeypatch.setattr(deployment_packages, "_BUSINESS_PLATFORM_REPO", business_repo)
    monkeypatch.setattr(deployment_packages, "_MICROSERVICE_REPO", microservice_repo)
    return task_repo, audit_repo, business_repo, microservice_repo


def _check(payload: dict, name: str) -> dict:
    return next(item for item in payload["checks"] if item["name"] == name)
