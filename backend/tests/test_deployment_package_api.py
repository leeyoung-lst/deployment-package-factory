from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from deployment_package_factory.api import deployment_packages


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(deployment_packages.router)
    return TestClient(app)


def test_deployment_package_options_returns_catalog() -> None:
    response = _client().get("/api/deployment-packages/options")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "k8s" in payload["deployModes"]
    assert any(item["key"] == "iam" for item in payload["platformServices"])
    assert any(item["key"] == "eam" for item in payload["businessServices"])
    assert any(item["key"] == "postgres" for item in payload["databaseOptions"])


def test_deployment_package_preview_returns_resolved_dependencies() -> None:
    response = _client().post(
        "/api/deployment-packages/preview",
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "platformServices": [],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "database": "postgres",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    platform_keys = {item["key"] for item in payload["platformServices"]}
    middleware_keys = {item["key"] for item in payload["middleware"]}
    assert {"iam", "gateway-frontend", "file-documents", "workflow-camunda", "audit"}.issubset(platform_keys)
    assert {"postgres", "redis", "minio", "camunda", "iotdb"}.issubset(middleware_keys)
    assert "local-ai-eam-service" in payload["images"]["business"]


def test_deployment_package_preview_rejects_unknown_database() -> None:
    response = _client().post(
        "/api/deployment-packages/preview",
        json={"database": "mysql"},
    )

    assert response.status_code == 400
    assert "Unsupported database option" in response.text


def test_create_get_and_download_deployment_package(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    original_builder = deployment_packages.build_deployment_package
    monkeypatch.setattr(deployment_packages, "_TASKS", {})
    monkeypatch.setattr(
        deployment_packages,
        "build_deployment_package",
        lambda payload: original_builder(payload, output_dir=tmp_path),
    )
    client = _client()

    created = client.post(
        "/api/deployment-packages",
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s", "docker-compose"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "database": "postgres",
        },
    )

    assert created.status_code == 200, created.text
    package_id = created.json()["packageId"]

    fetched = client.get(f"/api/deployment-packages/{package_id}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["packageId"] == package_id

    downloaded = client.get(f"/api/deployment-packages/{package_id}/download")
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"] == "application/gzip"


def test_create_deployment_package_returns_400_when_image_export_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deployment_packages, "_TASKS", {})
    monkeypatch.setattr(
        deployment_packages,
        "build_deployment_package",
        lambda payload: (_ for _ in ()).throw(deployment_packages.PackageBuildError("Docker CLI is not available.")),
    )

    response = _client().post(
        "/api/deployment-packages",
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam"}],
            "database": "postgres",
            "imageMode": "image-archive",
        },
    )

    assert response.status_code == 400
    assert "Docker CLI is not available" in response.text
