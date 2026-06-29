from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from deployment_package_factory.api import deployment_packages
from deployment_package_factory.services.deployment_packages import builder, runtime_options, task_executor
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import RegisteredBusinessPlatform
from deployment_package_factory.services.deployment_packages.models import BusinessSelection, PackageBuildRequest, PackageBuildResult
from deployment_package_factory.services.deployment_packages.task_executor import PackageTaskExecutor, PackageTaskExecutorConfig
from deployment_package_factory.services.microservices.scaffold import MicroserviceScaffoldRequest, MicroserviceScaffoldResult
from fakes import InMemoryAuditEventRepository, InMemoryBusinessPlatformRepository, InMemoryMicroserviceRepository, InMemoryTaskRepository


@pytest.fixture(autouse=True)
def _isolate_repositories(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(deployment_packages, "_BUSINESS_PLATFORM_REPO", InMemoryBusinessPlatformRepository())
    monkeypatch.setattr(deployment_packages, "_MICROSERVICE_REPO", InMemoryMicroserviceRepository())
    monkeypatch.setattr(deployment_packages, "_TASK_REPO", None)
    monkeypatch.setattr(deployment_packages, "_AUDIT_REPO", None)
    monkeypatch.setattr(deployment_packages, "_TASK_EXECUTOR", None)
    monkeypatch.setattr(builder, "_default_microservice_repository", deployment_packages.get_microservice_repository)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(deployment_packages.router)
    return TestClient(app)


def test_deployment_package_options_returns_no_fake_catalog_data() -> None:
    response = _client().get("/api/deployment-packages/options")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "k8s" in payload["deployModes"]
    assert payload["sourceEnvs"] == []
    assert payload["platformServices"] == []
    assert payload["businessServices"] == []
    assert payload["databaseOptions"] == []
    assert payload["middleware"] == []
    assert payload["projects"] == []


def test_deployment_package_options_returns_only_runtime_services(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)

    response = _client().get("/api/deployment-packages/options")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sourceEnvs"] == ["test"]
    assert {item["key"] for item in payload["platformServices"]} == {
        "ai-agent",
        "audit",
        "file-documents",
        "gateway-frontend",
        "iam",
        "observability",
        "workflow-camunda",
    }
    assert [item["key"] for item in payload["businessServices"]] == ["eam"]
    assert payload["businessServices"][0]["namespace"] == "test-biz-eam-4x60"
    assert payload["businessServices"][0]["sourceEnv"] == "test"
    assert {item["key"] for item in payload["databaseOptions"]} == {"postgres"}
    assert {item["key"] for item in payload["middleware"]} == {"camunda", "iotdb", "minio", "monitoring", "redis"}
    assert [item["key"] for item in payload["projects"]] == ["test-eam-4x60"]
    assert payload["projects"][0]["registry"] == "192.168.10.210/local-ai"


def test_deployment_package_options_discovers_kubernetes_business_namespaces(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch, seed_business=False)
    monkeypatch.setattr(
        deployment_packages,
        "list_registered_business_platforms",
        lambda include_disabled=False: [
            RegisteredBusinessPlatform(
                key="eam",
                name="EAM",
                profile="4x60",
                namespace="test-biz-eam-4x60",
                source_env="test",
                status="active",
            )
        ],
    )

    response = _client().get("/api/deployment-packages/options")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sourceEnvs"] == ["test"]
    assert payload["businessServices"][0]["namespace"] == "test-biz-eam-4x60"
    assert payload["projects"][0]["key"] == "test-eam-4x60"


def test_deployment_package_api_requires_token_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_API_TOKEN", "secret-token")

    response = _client().get("/api/deployment-packages/options")

    assert response.status_code == 401


def test_deployment_package_api_accepts_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_API_TOKEN", "secret-token")

    response = _client().get(
        "/api/deployment-packages/options",
        headers={"Authorization": "Bearer secret-token"},
    )

    assert response.status_code == 200, response.text


def test_deployment_package_api_accepts_header_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_API_TOKEN", "secret-token")

    response = _client().get(
        "/api/deployment-packages/options",
        headers={"X-Deployment-Package-Token": "secret-token"},
    )

    assert response.status_code == 200, response.text


def test_deployment_package_api_rejects_query_token_for_json_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_API_TOKEN", "secret-token")

    response = _client().get("/api/deployment-packages/options?deployment_package_token=secret-token")

    assert response.status_code == 401


def test_deployment_package_preview_returns_resolved_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)

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
    assert "192.168.10.210/local-ai/mqtt-collector:k8s" in payload["images"]["business"]


def test_deployment_package_preview_returns_runtime_image_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)

    response = _client().post(
        "/api/deployment-packages/preview",
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "database": "postgres",
            "targetProfile": {"registry": "harbor.prod/local-ai"},
        },
    )

    assert response.status_code == 200, response.text
    by_catalog = {item["catalogRef"]: item for item in response.json()["imageEntries"]}
    assert by_catalog["local-ai-eam-service:prod"]["sourceRef"] == "192.168.10.210/local-ai/local-ai-eam-service:k8s"
    assert by_catalog["local-ai-eam-service:prod"]["sourceResolvedFrom"] == "kubernetes"
    assert by_catalog["192.168.10.210/local-ai/mqtt-collector:k8s"]["sourceRef"] == "192.168.10.210/local-ai/mqtt-collector:k8s"
    assert by_catalog["192.168.10.210/local-ai/mqtt-collector:k8s"]["group"] == "business"


def test_deployment_package_preview_includes_registered_microservices(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)
    deployment_packages.get_microservice_repository().upsert(
        _microservice_request(),
        _microservice_result(),
    )

    response = _client().post(
        "/api/deployment-packages/preview",
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "database": "postgres",
            "targetProfile": {"registry": "harbor.prod/local-ai"},
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    by_catalog = {item["catalogRef"]: item for item in payload["imageEntries"]}
    assert "registry.local/business/asset-service" in payload["images"]["business"]
    assert by_catalog["registry.local/business/asset-service:prod"]["group"] == "business"
    assert by_catalog["registry.local/business/asset-service:prod"]["targetRef"] == "harbor.prod/local-ai/business/asset-service:prod"


def test_deployment_package_preview_can_select_observability(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)

    response = _client().post(
        "/api/deployment-packages/preview",
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "platformServices": ["observability"],
            "businessServices": [],
            "database": "postgres",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "observability" in {item["key"] for item in payload["platformServices"]}
    assert "monitoring" in {item["key"] for item in payload["middleware"]}


def test_register_and_disable_business_platform_api(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    repo = InMemoryTaskRepository()
    audit_repo = _set_repo(monkeypatch, repo, tmp_path)
    registered = RegisteredBusinessPlatform(
        key="eam",
        name="EAM",
        profile="4x60",
        namespace="test-biz-eam-4x60",
        source_env="test",
        status="active",
    )
    disabled = RegisteredBusinessPlatform(
        key="eam",
        name="EAM",
        profile="4x60",
        namespace="test-biz-eam-4x60",
        source_env="test",
        status="disabled",
    )
    monkeypatch.setattr(deployment_packages, "register_business_platform", lambda source_env, key, name, profile: registered)
    monkeypatch.setattr(deployment_packages, "disable_business_platform", lambda source_env, business_key, profile="": disabled)

    created = _client().post(
        "/api/deployment-packages/business-platforms/register",
        json={"sourceEnv": "test", "key": "eam", "name": "EAM", "profile": "4x60"},
    )
    removed = _client().post("/api/deployment-packages/business-platforms/test/eam/disable")

    assert created.status_code == 200, created.text
    assert created.json()["namespace"] == "test-biz-eam-4x60"
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "disabled"
    actions = [event.action for event in audit_repo.list(limit=10)]
    assert "business-platform.register" in actions
    assert "business-platform.disable" in actions


def test_preview_allows_kubernetes_discovered_business_without_db_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch, seed_business=False)
    monkeypatch.setattr(
        deployment_packages,
        "list_registered_business_platforms",
        lambda include_disabled=False: [
            RegisteredBusinessPlatform(
                key="eam",
                name="EAM",
                profile="4x60",
                namespace="test-biz-eam-4x60",
                source_env="test",
                status="active",
            )
        ],
    )

    response = _client().post(
        "/api/deployment-packages/preview",
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "database": "postgres",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["businessServices"][0]["key"] == "eam"


def test_preview_accepts_runtime_discovered_project_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)

    options = _client().get("/api/deployment-packages/options")
    assert options.status_code == 200, options.text
    project = options.json()["projects"][0]

    response = _client().post(
        "/api/deployment-packages/preview",
        json={
            "projectKey": project["key"],
            "productVersion": project["defaultVersion"],
            "sourceEnv": project["defaultSourceEnv"],
            "deployModes": project["defaultDeployModes"],
            "platformServices": project["defaultPlatformServices"],
            "businessServices": project["defaultBusinessServices"],
            "database": project["defaultDatabase"],
            "targetProfile": {"registry": "harbor.prod/local-ai"},
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["businessServices"][0]["key"] == "eam"
    by_catalog = {item["catalogRef"]: item for item in payload["imageEntries"]}
    assert by_catalog["local-ai-eam-service:k8s"]["sourceResolvedFrom"] == "kubernetes"
    assert by_catalog["192.168.10.210/local-ai/nginx:1.27-alpine"]["sourceRef"] == "192.168.10.210/local-ai/nginx:1.27-alpine"


def test_deployment_package_preview_rejects_unknown_database() -> None:
    response = _client().post(
        "/api/deployment-packages/preview",
        json={"database": "mysql"},
    )

    assert response.status_code == 400
    assert "Unsupported database option" in response.text


def test_image_export_environment_api_reports_docker_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        deployment_packages,
        "check_image_export_environment",
        lambda: deployment_packages.ImageExportEnvironmentCheck(
            available=True,
            exportTool="skopeo",
            toolVersion="skopeo version 1.14.0",
            message="ready",
        ),
    )

    response = _client().get("/api/deployment-packages/image-export-environment")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "available": True,
        "exportTool": "skopeo",
        "toolVersion": "skopeo version 1.14.0",
        "dockerVersion": "",
        "message": "ready",
    }


def test_create_get_and_download_deployment_package(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)
    repo = InMemoryTaskRepository()
    audit_repo = _set_repo(monkeypatch, repo, tmp_path)
    monkeypatch.setattr(
        task_executor,
        "build_deployment_package",
        lambda payload, output_dir=None: builder.build_deployment_package(payload, output_dir=tmp_path),
    )
    client = _client()

    created = client.post(
        "/api/deployment-packages",
        headers={"X-Deployment-Package-Operator": "alice"},
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
    assert downloaded.headers["content-length"] == str(task["result"]["artifactSize"])
    assert f"local-ai-prod-package-{package_id}.tar.gz" in downloaded.headers["content-disposition"]
    assert downloaded.headers["x-deployment-package-sha256"] == task["result"]["sha256"]
    assert downloaded.content

    checksum = client.get(f"/api/deployment-packages/{package_id}/checksum")
    assert checksum.status_code == 200, checksum.text
    assert checksum.headers["content-type"].startswith("text/plain")
    assert checksum.headers["x-deployment-package-sha256"] == task["result"]["sha256"]
    assert checksum.text.strip() == f"{task['result']['sha256']}  local-ai-prod-package-{package_id}.tar.gz"
    events = audit_repo.list(limit=10)
    actions = [event.action for event in events]
    assert "package.create" in actions
    assert "package.download" in actions
    assert "package.checksum.download" in actions
    created_event = next(event for event in events if event.action == "package.create")
    assert created_event.operator == "alice"
    assert created_event.metadata["database"] == "postgres"


def test_download_deployment_package_accepts_query_token(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_API_TOKEN", "secret-token")
    _mock_runtime_environment(monkeypatch)
    task_repo = InMemoryTaskRepository()
    _set_repo(monkeypatch, task_repo, tmp_path)
    monkeypatch.setattr(
        task_executor,
        "build_deployment_package",
        lambda payload, output_dir=None: builder.build_deployment_package(payload, output_dir=tmp_path),
    )
    client = _client()
    created = client.post(
        "/api/deployment-packages",
        headers={"Authorization": "Bearer secret-token"},
        json={"sourceEnv": "test", "deployModes": ["k8s"], "businessServices": [{"name": "eam", "profile": "4x60"}]},
    )

    assert created.status_code == 200, created.text
    task = _wait_for_task(client, created.json()["taskId"], headers={"Authorization": "Bearer secret-token"})
    package_id = task["result"]["packageId"]

    downloaded = client.get(f"/api/deployment-packages/{package_id}/download?deployment_package_token=secret-token")

    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"] == "application/gzip"
    assert downloaded.headers["content-length"] == str(task["result"]["artifactSize"])
    assert downloaded.content


def test_create_deployment_package_worker_mode_leaves_task_pending(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)
    repo = InMemoryTaskRepository()
    _set_repo(monkeypatch, repo, tmp_path)
    monkeypatch.setattr(deployment_packages, "_SETTINGS", replace(deployment_packages._SETTINGS, execution_mode="worker"))

    response = _client().post(
        "/api/deployment-packages",
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "database": "postgres",
        },
    )

    assert response.status_code == 200, response.text
    task = repo.get(response.json()["taskId"])
    assert task is not None
    assert task.status == "pending"


def test_create_deployment_package_returns_400_when_image_export_fails(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)
    repo = InMemoryTaskRepository()
    _set_repo(monkeypatch, repo, tmp_path)
    monkeypatch.setattr(
        task_executor,
        "build_deployment_package",
        lambda payload, output_dir=None: (_ for _ in ()).throw(builder.PackageBuildError("Docker CLI is not available.")),
    )

    response = _client().post(
        "/api/deployment-packages",
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "database": "postgres",
            "imageMode": "image-archive",
        },
    )

    assert response.status_code == 200
    task = _wait_for_task(_client(), response.json()["taskId"])
    assert task["status"] == "failed"
    assert "Docker CLI is not available" in task["error"]


def test_create_deployment_package_rejects_invalid_image_mode() -> None:
    response = _client().post(
        "/api/deployment-packages",
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam"}],
            "database": "postgres",
            "imageMode": "none",
        },
    )

    assert response.status_code == 422
    assert "imageMode" in response.text


def test_cancel_pending_deployment_package_task(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTaskRepository()
    audit_repo = _set_repo(monkeypatch, repo, tmp_path)
    task = repo.create(deployment_packages.PackageBuildRequest())

    response = _client().post(f"/api/deployment-packages/tasks/{task.task_id}/cancel")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "canceled"
    events = audit_repo.list(limit=10)
    assert events[0].action == "task.cancel"
    assert events[0].target_id == task.task_id


def test_cleanup_deployment_package_outputs_api(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTaskRepository()
    audit_repo = _set_repo(monkeypatch, repo, tmp_path)

    response = _client().post("/api/deployment-packages/cleanup?dry_run=true")

    assert response.status_code == 200, response.text
    assert response.json()["dryRun"] is True
    assert response.json()["scannedTasks"] == 0
    events = audit_repo.list(limit=10)
    assert events[0].action == "package.cleanup"
    assert events[0].status == "dry-run"
    assert events[0].metadata["dryRun"] is True


def test_retry_failed_deployment_package_task(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTaskRepository()
    audit_repo = _set_repo(monkeypatch, repo, tmp_path)
    monkeypatch.setattr(
        task_executor,
        "build_deployment_package",
        lambda payload, output_dir=None: (_ for _ in ()).throw(builder.PackageBuildError("still failing")),
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
    events = audit_repo.list(limit=10)
    retry_event = next(event for event in events if event.action == "task.retry")
    assert retry_event.target_id == retry_task_id
    assert retry_event.metadata["sourceTaskId"] == task.task_id


def test_running_task_cancel_request_discards_result(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTaskRepository()
    _set_repo(monkeypatch, repo, tmp_path)
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
    monkeypatch.setattr(task_executor, "build_deployment_package", lambda payload, output_dir=None: result)

    with TestClient(_app()) as client:
        response = client.post(f"/api/deployment-packages/tasks/{task.task_id}/retry")

    assert response.status_code == 409

    import asyncio

    asyncio.run(deployment_packages.get_task_executor().run(task.task_id, PackageBuildRequest()))

    reloaded = repo.get(task.task_id)
    assert reloaded is not None
    assert reloaded.status == "canceled"
    assert reloaded.result is None


def test_list_deployment_package_tasks(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTaskRepository()
    _set_repo(monkeypatch, repo, tmp_path)
    repo.create(deployment_packages.PackageBuildRequest())

    response = _client().get("/api/deployment-packages/tasks")

    assert response.status_code == 200, response.text
    assert response.json()


def test_list_deployment_package_audit_events(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTaskRepository()
    audit_repo = _set_repo(monkeypatch, repo, tmp_path)
    audit_repo.record(action="package.create", status="accepted", target_id="task-1")

    response = _client().get("/api/deployment-packages/audit-events")

    assert response.status_code == 200, response.text
    assert response.json()[0]["action"] == "package.create"


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(deployment_packages.router)
    return app


def _set_repo(monkeypatch: pytest.MonkeyPatch, repo: InMemoryTaskRepository, output_dir) -> InMemoryAuditEventRepository:
    audit_repo = InMemoryAuditEventRepository()
    monkeypatch.setattr(deployment_packages, "_TASK_REPO", repo)
    monkeypatch.setattr(deployment_packages, "_AUDIT_REPO", audit_repo)
    monkeypatch.setattr(
        deployment_packages,
        "_TASK_EXECUTOR",
        PackageTaskExecutor(repo, PackageTaskExecutorConfig(max_concurrent_builds=1, output_dir=output_dir)),
    )
    return audit_repo


def _microservice_request() -> MicroserviceScaffoldRequest:
    return MicroserviceScaffoldRequest(
        serviceKey="asset-service",
        serviceName="Asset Service",
        sourceEnv="test",
        businessPlatformKey="eam",
        businessPlatformProfile="4x60",
        businessPlatformName="EAM",
        businessPlatformNamespace="test-biz-eam-4x60",
        imageRegistry="registry.local",
        imageNamespace="business",
        port=8000,
        middleware=["redis", "postgresql"],
    )


def _microservice_result() -> MicroserviceScaffoldResult:
    return MicroserviceScaffoldResult(
        projectId="svc-test",
        serviceKey="asset-service",
        serviceName="Asset Service",
        techStack="python-fastapi",
        sourceEnv="test",
        businessPlatformKey="eam",
        businessPlatformProfile="4x60",
        businessPlatformName="EAM",
        businessPlatformNamespace="test-biz-eam-4x60",
        artifactName="asset-service.tar.gz",
        artifactPath="/tmp/asset-service.tar.gz",
        artifactSize=1,
        sha256="abc",
        downloadUrl="/api/microservices/svc-test/download",
        downloadCommand="curl -o asset-service.tar.gz /api/microservices/svc-test/download",
        cloneCommand="git clone file:///tmp/asset-service",
        generatedFiles=[],
    )


def _mock_runtime_environment(monkeypatch: pytest.MonkeyPatch, *, seed_business: bool = True) -> None:
    registered = [
        RegisteredBusinessPlatform(
            key="eam",
            name="EAM",
            profile="4x60",
            namespace="test-biz-eam-4x60",
            source_env="test",
            status="active",
        )
    ]
    runtime_images = [
        ("192.168.10.210/local-ai/local-ai-iam-service:k8s", "iam"),
        ("192.168.10.210/local-ai/local-ai-backend:k8s", "backend"),
        ("192.168.10.210/local-ai/local-ai-frontend:k8s", "frontend"),
        ("192.168.10.210/local-ai/local-ai-eam-service:k8s", "eam"),
        ("192.168.10.210/local-ai/sub-app-eam:k8s", "sub-eam"),
        ("192.168.10.210/local-ai/local-ai-collection-service:k8s", "collection"),
        ("192.168.10.210/local-ai/mqtt-collector:k8s", "mqtt"),
        ("192.168.10.210/local-ai/dnc-modbus-simulator:k8s", "modbus"),
        ("192.168.10.210/local-ai/postgres:16", "postgres"),
        ("192.168.10.210/local-ai/redis:7", "redis"),
        ("192.168.10.210/local-ai/minio/minio:latest", "minio"),
        ("192.168.10.210/local-ai/camunda/camunda:latest", "camunda"),
        ("192.168.10.210/local-ai/apache/iotdb:latest", "iotdb"),
        ("192.168.10.210/local-ai/prometheus:latest", "prometheus"),
    ]

    if seed_business:
        repo = InMemoryBusinessPlatformRepository()
        for item in registered:
            repo.upsert_registered(item)
        monkeypatch.setattr(deployment_packages, "_BUSINESS_PLATFORM_REPO", repo)

    monkeypatch.setattr(
        runtime_options,
        "source_env_namespaces",
        lambda source_env, business_namespaces=None: ["local-ai", *(business_namespaces or [])] if source_env == "test" else [],
    )
    monkeypatch.setattr(
        deployment_packages.package_builder,
        "_source_env_namespaces",
        lambda source_env, business_namespaces=None: ["local-ai", *(business_namespaces or [])] if source_env == "test" else [],
    )
    monkeypatch.setattr(
        builder,
        "_source_env_namespaces",
        lambda source_env, business_namespaces=None: ["local-ai", *(business_namespaces or [])] if source_env == "test" else [],
    )
    monkeypatch.setattr(
        builder,
        "_list_runtime_images",
        lambda namespaces: [
            builder.RuntimeSourceImage(
                source_ref=image,
                image_id=f"{image.rsplit(':', 1)[0]}@sha256:{digest}",
                namespace=namespaces[0] if namespaces else "local-ai",
                pod=f"{digest}-pod",
                container=digest,
            )
            for image, digest in runtime_images
        ],
    )


def _wait_for_task(client: TestClient, task_id: str, headers: dict[str, str] | None = None) -> dict:
    for _ in range(50):
        response = client.get(f"/api/deployment-packages/tasks/{task_id}", headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in {"completed", "failed", "canceled"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Task {task_id} did not finish")
