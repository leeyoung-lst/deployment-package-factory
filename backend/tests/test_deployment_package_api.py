from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from deployment_package_factory.api import deployment_packages
from deployment_package_factory.services.deployment_packages.models import BusinessSelection, PackageBuildRequest, PackageBuildResult
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository


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
    assert any(item["key"] == "standard-eam" for item in payload["projects"])


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
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    monkeypatch.setattr(deployment_packages, "_TASK_REPO", repo)
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
    task_id = created.json()["taskId"]
    task = _wait_for_task(client, task_id)
    assert task["status"] == "completed"
    assert task["result"]
    package_id = task["result"]["packageId"]

    fetched = client.get(f"/api/deployment-packages/{package_id}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["packageId"] == package_id

    fetched_by_task = client.get(f"/api/deployment-packages/{task_id}")
    assert fetched_by_task.status_code == 200, fetched_by_task.text
    assert fetched_by_task.json()["packageId"] == package_id

    downloaded = client.get(f"/api/deployment-packages/{package_id}/download")
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"] == "application/gzip"


def test_create_deployment_package_returns_400_when_image_export_fails(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    monkeypatch.setattr(deployment_packages, "_TASK_REPO", repo)
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

    assert response.status_code == 200
    task = _wait_for_task(_client(), response.json()["taskId"])
    assert task["status"] == "failed"
    assert "Docker CLI is not available" in task["error"]


def test_cancel_pending_deployment_package_task(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    monkeypatch.setattr(deployment_packages, "_TASK_REPO", repo)
    task = repo.create(deployment_packages.PackageBuildRequest())

    response = _client().post(f"/api/deployment-packages/tasks/{task.task_id}/cancel")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "canceled"


def test_retry_failed_deployment_package_task(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    monkeypatch.setattr(deployment_packages, "_TASK_REPO", repo)
    monkeypatch.setattr(
        deployment_packages,
        "build_deployment_package",
        lambda payload: (_ for _ in ()).throw(deployment_packages.PackageBuildError("still failing")),
    )
    task = repo.create(PackageBuildRequest(businessServices=[BusinessSelection(name="eam")]))
    repo.mark_failed(task.task_id, "failed once")

    response = _client().post(f"/api/deployment-packages/tasks/{task.task_id}/retry")

    assert response.status_code == 200, response.text
    retry_task_id = response.json()["taskId"]
    assert retry_task_id != task.task_id
    retry_task = _wait_for_task(_client(), retry_task_id)
    assert retry_task["status"] == "failed"
    assert "still failing" in retry_task["error"]


def test_running_task_cancel_request_discards_result(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    monkeypatch.setattr(deployment_packages, "_TASK_REPO", repo)
    task = repo.create(PackageBuildRequest())
    repo.mark_running(task.task_id)
    repo.cancel(task.task_id)
    result = PackageBuildResult(
        packageId="pkg-canceled",
        workDir="/tmp/work",
        artifactPath="/tmp/pkg.tar.gz",
        sha256="abc",
        manifest={},
    )
    monkeypatch.setattr(deployment_packages, "build_deployment_package", lambda payload: result)

    with TestClient(_app()) as client:
        response = client.post(f"/api/deployment-packages/tasks/{task.task_id}/retry")

    assert response.status_code == 409

    import asyncio

    asyncio.run(deployment_packages._run_package_task(task.task_id, PackageBuildRequest()))

    reloaded = repo.get(task.task_id)
    assert reloaded is not None
    assert reloaded.status == "canceled"
    assert reloaded.result is None


def test_list_deployment_package_tasks(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = PackageTaskRepository(tmp_path / "tasks.sqlite3")
    monkeypatch.setattr(deployment_packages, "_TASK_REPO", repo)
    repo.create(deployment_packages.PackageBuildRequest())

    response = _client().get("/api/deployment-packages/tasks")

    assert response.status_code == 200, response.text
    assert response.json()


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(deployment_packages.router)
    return app


def _wait_for_task(client: TestClient, task_id: str) -> dict:
    for _ in range(50):
        response = client.get(f"/api/deployment-packages/tasks/{task_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Task {task_id} did not finish")
