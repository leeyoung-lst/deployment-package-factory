from __future__ import annotations

import tarfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from deployment_package_factory.api import deployment_packages, microservices
from deployment_package_factory.services.deployment_packages.business_platform_repository import BusinessPlatformRepository
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import RegisteredBusinessPlatform
from deployment_package_factory.services.microservices.repository import MicroserviceRepository


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(microservices.router)
    return TestClient(app)


def test_register_microservice_requires_registered_business_platform(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        deployment_packages,
        "_BUSINESS_PLATFORM_REPO",
        BusinessPlatformRepository(tmp_path / "business-platforms.sqlite3"),
    )

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-service",
            "serviceName": "Asset Service",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "middleware": ["redis", "postgresql"],
        },
    )

    assert response.status_code == 404
    assert "Business platform is not registered" in response.text


def test_register_microservice_generates_fastapi_project_for_business_platform(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path))
    repo = BusinessPlatformRepository(tmp_path / "business-platforms.sqlite3")
    microservice_repo = MicroserviceRepository(tmp_path / "microservices.sqlite3")
    repo.upsert_registered(
        RegisteredBusinessPlatform(
            key="eam",
            name="EAM",
            profile="4x60",
            namespace="test-biz-eam-4x60",
            source_env="test",
            status="active",
        )
    )
    monkeypatch.setattr(deployment_packages, "_BUSINESS_PLATFORM_REPO", repo)
    monkeypatch.setattr(deployment_packages, "_MICROSERVICE_REPO", microservice_repo)

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-service",
            "serviceName": "Asset Service",
            "description": "Asset domain service",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
            "middleware": ["redis", "postgresql"],
            "imageRegistry": "registry.local",
            "imageNamespace": "business",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["businessPlatformKey"] == "eam"
    assert payload["businessPlatformNamespace"] == "test-biz-eam-4x60"
    artifact = Path(payload["artifactPath"])
    assert artifact.exists()

    with tarfile.open(artifact, "r:gz") as tar:
        names = set(tar.getnames())
        assert "asset-service/README.md" in names
        assert "asset-service/Dockerfile" in names
        assert "asset-service/Jenkinsfile" in names
        assert "asset-service/.env.template" in names
        assert "asset-service/src/app/main.py" in names
        assert "asset-service/src/app/services/redis_client.py" in names
        assert "asset-service/src/app/repositories/postgres.py" in names
        assert "asset-service/deploy/k8s/deployment.yaml" in names
        readme = tar.extractfile("asset-service/README.md").read().decode("utf-8")
        env_template = tar.extractfile("asset-service/.env.template").read().decode("utf-8")
        deployment = tar.extractfile("asset-service/deploy/k8s/deployment.yaml").read().decode("utf-8")

    assert "Platform: EAM (eam)" in readme
    assert "BUSINESS_PLATFORM_KEY=eam" in env_template
    assert "BUSINESS_PLATFORM_NAMESPACE=test-biz-eam-4x60" in env_template
    assert "business-platform: eam" in deployment

    listed = _client().get("/api/microservices?source_env=test&business_platform_key=eam&business_platform_profile=4x60")

    assert listed.status_code == 200, listed.text
    services = listed.json()
    assert len(services) == 1
    assert services[0]["serviceKey"] == "asset-service"
    assert services[0]["businessPlatformNamespace"] == "test-biz-eam-4x60"
    assert services[0]["image"] == "registry.local/business/asset-service"

    app = FastAPI()
    app.include_router(deployment_packages.router)
    options = TestClient(app).get("/api/deployment-packages/options")

    assert options.status_code == 200, options.text
    assert options.json()["microservices"][0]["serviceKey"] == "asset-service"
