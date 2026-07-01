from __future__ import annotations

from fastapi.testclient import TestClient

from deployment_package_factory.api import _common, settings
from deployment_package_factory.main import create_app
from deployment_package_factory.services.deployment_packages.models import ImageExportEnvironmentCheck
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest
from deployment_package_factory.services.settings import SystemSettings
from fakes import InMemoryAuditEventRepository, InMemoryBusinessPlatformRepository, InMemoryMicroserviceRepository, InMemoryTaskRepository


def test_metrics_endpoint_exports_prometheus_text(tmp_path, monkeypatch) -> None:
    task_repo = InMemoryTaskRepository()
    audit_repo = InMemoryAuditEventRepository()
    task_repo.create(PackageBuildRequest())
    audit_repo.record(action="package.create", status="accepted")
    monkeypatch.setattr(_common, "_TASK_REPO", task_repo)
    monkeypatch.setattr(_common, "_AUDIT_REPO", audit_repo)

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


def test_settings_api_gets_and_updates_system_settings(monkeypatch) -> None:
    repo = InMemorySystemSettingsRepository()
    monkeypatch.setattr(settings, "_SETTINGS_REPO", repo)

    client = TestClient(create_app())
    response = client.get("/api/settings")

    assert response.status_code == 200, response.text
    assert response.json()["git"]["group"] == "business-services"
    assert response.json()["harbor"]["registry"] == "registry.local"

    updated = client.put(
        "/api/settings",
        json={
            "git": {"baseUrl": " http://gitlab.local/ ", "group": " /Business/EAM/ ", "username": " dev ", "email": "dev@example.local "},
            "harbor": {"registry": " harbor.local:5000/ ", "project": " /Business/EAM/ ", "username": " robot ", "insecure": True},
            "jenkins": {"baseUrl": " http://jenkins.local/ ", "folder": " /Business/EAM/ ", "username": " ci "},
        },
    )

    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["git"]["baseUrl"] == "http://gitlab.local/"
    assert payload["git"]["group"] == "business/eam"
    assert payload["harbor"]["registry"] == "harbor.local:5000"
    assert payload["harbor"]["project"] == "business/eam"
    assert payload["jenkins"]["folder"] == "business/eam"


class InMemorySystemSettingsRepository:
    def __init__(self) -> None:
        self.value = SystemSettings()

    def get(self) -> SystemSettings:
        return self.value

    def update(self, settings_value: SystemSettings) -> SystemSettings:
        self.value = settings_value.model_copy(update={"updated_at": "now"})
        return self.value


def _set_ready_repositories(monkeypatch):
    task_repo = InMemoryTaskRepository()
    audit_repo = InMemoryAuditEventRepository()
    business_repo = InMemoryBusinessPlatformRepository()
    microservice_repo = InMemoryMicroserviceRepository()
    monkeypatch.setattr(_common, "_TASK_REPO", task_repo)
    monkeypatch.setattr(_common, "_AUDIT_REPO", audit_repo)
    monkeypatch.setattr(_common, "_BUSINESS_PLATFORM_REPO", business_repo)
    monkeypatch.setattr(_common, "_MICROSERVICE_REPO", microservice_repo)
    return task_repo, audit_repo, business_repo, microservice_repo


def _check(payload: dict, name: str) -> dict:
    return next(item for item in payload["checks"] if item["name"] == name)
