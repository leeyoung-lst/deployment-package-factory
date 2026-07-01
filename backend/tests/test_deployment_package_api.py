from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from deployment_package_factory.api import _common, business_platforms, deployment_packages, downloads
from deployment_package_factory.services.deployment_packages import builder, runtime_options, task_executor
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import RegisteredBusinessPlatform
from deployment_package_factory.services.deployment_packages.models import BusinessSelection, PackageBuildRequest, PackageBuildResult
from deployment_package_factory.services.deployment_packages.task_executor import PackageTaskExecutor, PackageTaskExecutorConfig
from deployment_package_factory.services.microservices.scaffold import MicroserviceScaffoldRequest, MicroserviceScaffoldResult
from fakes import InMemoryAuditEventRepository, InMemoryBusinessPlatformRepository, InMemoryMicroserviceRepository, InMemoryTaskRepository


@pytest.fixture(autouse=True)
def _isolate_repositories(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(_common, "_BUSINESS_PLATFORM_REPO", InMemoryBusinessPlatformRepository())
    monkeypatch.setattr(_common, "_MICROSERVICE_REPO", InMemoryMicroserviceRepository())
    monkeypatch.setattr(_common, "_TASK_REPO", None)
    monkeypatch.setattr(_common, "_AUDIT_REPO", None)
    monkeypatch.setattr(_common, "_TASK_EXECUTOR", None)
    monkeypatch.setattr(builder, "_default_microservice_repository", _common.get_microservice_repository)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(deployment_packages.router)
    app.include_router(downloads.router)
    app.include_router(business_platforms.router)
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
    assert {item["key"] for item in payload["middleware"]} == {
        "camunda",
        "camunda-elasticsearch",
        "iotdb",
        "minio",
        "monitoring",
        "redis",
    }
    assert [item["key"] for item in payload["projects"]] == ["test-eam-4x60"]
    assert payload["projects"][0]["registry"] == "192.168.10.210/local-ai"


def test_deployment_package_options_discovers_kubernetes_business_namespaces(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch, seed_business=False)
    monkeypatch.setattr(
        _common,
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
    assert {"postgres", "redis", "minio", "camunda", "camunda-elasticsearch", "iotdb"}.issubset(middleware_keys)
    assert "local-ai-eam-service" in payload["images"]["business"]
    assert "192.168.10.210/k8s-platform/docker.elastic.co/elasticsearch/elasticsearch:8.17.4" in payload["images"]["middleware"]
    assert "192.168.10.210/local-ai/mqtt-collector:k8s" in payload["images"]["business"]
    assert payload["runtimeConfig"]["resources"]
    database_resources = [item for item in payload["runtimeConfig"]["resources"] if item["type"] == "databaseSchema"]
    assert database_resources[0]["items"][0]["label"] == "数据库名"
    assert any(group["key"] == "postgres" for group in payload["runtimeConfig"]["groups"])
    postgres = next(group for group in payload["runtimeConfig"]["groups"] if group["key"] == "postgres")
    database_password = next(item for item in postgres["items"] if item["name"] == "DATABASE_PASSWORD")
    assert database_password["value"] == "source-db-password"
    assert database_password["source"] == "source-secret"


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
    _common.get_microservice_repository().upsert(
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
    assert "registry.local/business/asset-service:prod" in payload["images"]["business"]
    assert by_catalog["registry.local/business/asset-service:prod"]["group"] == "business"
    assert by_catalog["registry.local/business/asset-service:prod"]["targetRef"] == "harbor.prod/local-ai/business/asset-service:prod"


def test_deployment_package_preview_warns_for_unbuilt_registered_microservice(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)
    _common.get_microservice_repository().upsert(
        _microservice_request(),
        _microservice_result(delivery=_delivery("failed")),
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
    assert any("asset-service" in warning and "failed" in warning for warning in response.json()["warnings"])


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
    monkeypatch.setattr(business_platforms, "register_business_platform", lambda source_env, key, name, profile: registered)
    monkeypatch.setattr(business_platforms, "disable_business_platform", lambda source_env, business_key, profile="": disabled)

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
        _common,
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
            "imageMode": "image-manifest",
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
    assert downloaded.headers["accept-ranges"] == "bytes"
    assert downloaded.headers["content-length"] == str(task["result"]["artifactSize"])
    assert downloaded.headers["etag"] == f'"{task["result"]["sha256"]}"'
    assert downloaded.headers["last-modified"]
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
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "imageMode": "image-manifest",
        },
    )

    assert created.status_code == 200, created.text
    task = _wait_for_task(client, created.json()["taskId"], headers={"Authorization": "Bearer secret-token"})
    package_id = task["result"]["packageId"]

    downloaded = client.get(f"/api/deployment-packages/{package_id}/download?deployment_package_token=secret-token")

    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"] == "application/gzip"
    assert downloaded.headers["content-length"] == str(task["result"]["artifactSize"])
    assert downloaded.content


def test_download_deployment_package_supports_range_resume(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "imageMode": "image-manifest",
        },
    )
    task = _wait_for_task(client, created.json()["taskId"])
    package_id = task["result"]["packageId"]
    artifact = Path(task["result"]["artifactPath"])
    expected = artifact.read_bytes()[10:26]

    response = client.get(f"/api/deployment-packages/{package_id}/download", headers={"Range": "bytes=10-25"})

    assert response.status_code == 206, response.text
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == "16"
    assert response.headers["content-range"] == f"bytes 10-25/{artifact.stat().st_size}"
    assert response.content == expected


def test_head_deployment_package_download_returns_resume_metadata(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "imageMode": "image-manifest",
        },
    )
    task = _wait_for_task(client, created.json()["taskId"])
    package_id = task["result"]["packageId"]

    response = client.head(f"/api/deployment-packages/{package_id}/download")

    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == str(task["result"]["artifactSize"])
    assert response.headers["etag"] == f'"{task["result"]["sha256"]}"'
    assert response.headers["last-modified"]
    assert response.content == b""


def test_download_deployment_package_honors_if_range(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "imageMode": "image-manifest",
        },
    )
    task = _wait_for_task(client, created.json()["taskId"])
    package_id = task["result"]["packageId"]
    artifact = Path(task["result"]["artifactPath"])
    etag = f'"{task["result"]["sha256"]}"'

    matched = client.get(f"/api/deployment-packages/{package_id}/download", headers={"Range": "bytes=0-3", "If-Range": etag})
    stale = client.get(f"/api/deployment-packages/{package_id}/download", headers={"Range": "bytes=0-3", "If-Range": '"stale"'})

    assert matched.status_code == 206, matched.text
    assert matched.content == artifact.read_bytes()[:4]
    assert stale.status_code == 200, stale.text
    assert stale.headers["content-length"] == str(artifact.stat().st_size)
    assert stale.content == artifact.read_bytes()


def test_download_deployment_package_scripts_include_resume_and_verify(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "imageMode": "image-manifest",
        },
    )
    task = _wait_for_task(client, created.json()["taskId"])
    package_id = task["result"]["packageId"]

    ps1 = client.get(f"/api/deployment-packages/{package_id}/download-script.ps1?deployment_package_token=abc")
    shell = client.get(f"/api/deployment-packages/{package_id}/download-script.sh")

    assert ps1.status_code == 200, ps1.text
    assert "ExecutionPolicy Bypass" in ps1.text
    assert f"http://testserver/api/deployment-packages/{package_id}/download?deployment_package_token=abc" in ps1.text
    assert "Range: bytes=$RangeStart-$End" in ps1.text
    assert "If-Range: $ETag" in ps1.text
    assert "curl failed with exit code" in ps1.text
    assert ".parts" in ps1.text
    assert "--retry 20" in ps1.text
    assert "Get-FileHash" in ps1.text
    assert "deployment_package_token=abc" in ps1.text
    assert shell.status_code == 200, shell.text
    assert f"http://testserver/api/deployment-packages/{package_id}/download" in shell.text
    assert 'part_dir="$package_file.parts"' in shell.text
    assert "-r \"$range_start-$end\"" in shell.text
    assert "sha256sum" in shell.text
    assert task["result"]["sha256"] in shell.text


def test_download_script_accepts_query_token(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "imageMode": "image-manifest",
        },
    )
    task = _wait_for_task(client, created.json()["taskId"], headers={"Authorization": "Bearer secret-token"})
    package_id = task["result"]["packageId"]

    response = client.get(f"/api/deployment-packages/{package_id}/download-script.ps1?deployment_package_token=secret-token")

    assert response.status_code == 200, response.text
    assert "deployment_package_token=secret-token" in response.text


def test_download_deployment_package_rejects_invalid_range(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "imageMode": "image-manifest",
        },
    )
    task = _wait_for_task(client, created.json()["taskId"])
    package_id = task["result"]["packageId"]

    response = client.get(f"/api/deployment-packages/{package_id}/download", headers={"Range": "bytes=999999999-"})

    assert response.status_code == 416
    assert response.headers["content-range"] == f"bytes */{task['result']['artifactSize']}"


def test_create_deployment_package_worker_mode_leaves_task_pending(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)
    repo = InMemoryTaskRepository()
    _set_repo(monkeypatch, repo, tmp_path)
    monkeypatch.setattr(_common, "_SETTINGS", replace(_common._SETTINGS, execution_mode="worker"))

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


def test_create_deployment_package_defaults_to_image_archive(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)
    repo = InMemoryTaskRepository()
    audit_repo = _set_repo(monkeypatch, repo, tmp_path)
    monkeypatch.setattr(_common, "_SETTINGS", replace(_common._SETTINGS, execution_mode="worker"))

    response = _client().post(
        "/api/deployment-packages",
        json={
            "sourceEnv": "test",
            "deployModes": ["docker-compose"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "database": "postgres",
        },
    )

    assert response.status_code == 200, response.text
    task = repo.get(response.json()["taskId"])
    assert task is not None
    assert task.request["imageMode"] == "image-archive"
    assert task.request["targetProfile"]["exportImages"] is True
    event = audit_repo.list(limit=1)[0]
    assert event.metadata["imageMode"] == "image-archive"


def test_create_deployment_package_rejects_unbuilt_registered_microservice(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_runtime_environment(monkeypatch)
    audit_repo = _set_repo(monkeypatch, InMemoryTaskRepository(), tmp_path)
    _common.get_microservice_repository().upsert(
        _microservice_request(),
        _microservice_result(delivery=_delivery("running")),
    )

    response = _client().post(
        "/api/deployment-packages",
        json={
            "sourceEnv": "test",
            "deployModes": ["k8s"],
            "businessServices": [{"name": "eam", "profile": "4x60"}],
            "database": "postgres",
        },
    )

    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "MICROSERVICE_DELIVERY_NOT_READY"
    assert detail["services"][0]["serviceKey"] == "asset-service"
    assert detail["services"][0]["buildStatus"] == "running"
    assert "Asset Service" in detail["message"]
    event = audit_repo.list(limit=1)[0]
    assert event.action == "package.create.blocked"
    assert event.status == "blocked"
    assert event.metadata["code"] == "MICROSERVICE_DELIVERY_NOT_READY"
    assert event.metadata["services"][0]["serviceKey"] == "asset-service"


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
    task = repo.create(PackageBuildRequest())

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


def test_retry_normalizes_legacy_manifest_task_to_image_archive(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTaskRepository()
    _set_repo(monkeypatch, repo, tmp_path)
    monkeypatch.setattr(_common, "_SETTINGS", replace(_common._SETTINGS, execution_mode="worker"))
    task = repo.create(
        PackageBuildRequest(
            businessServices=[BusinessSelection(name="eam")],
            imageMode="image-manifest",
        )
    )
    repo.mark_failed(task.task_id, "legacy manifest task failed")

    response = _client().post(f"/api/deployment-packages/tasks/{task.task_id}/retry")

    assert response.status_code == 200, response.text
    retry_task = repo.get(response.json()["taskId"])
    assert retry_task is not None
    assert retry_task.request["imageMode"] == "image-archive"
    assert retry_task.request["targetProfile"]["exportImages"] is True


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

    asyncio.run(_common.get_task_executor().run(task.task_id, PackageBuildRequest()))

    reloaded = repo.get(task.task_id)
    assert reloaded is not None
    assert reloaded.status == "canceled"
    assert reloaded.result is None


def test_list_deployment_package_tasks(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTaskRepository()
    _set_repo(monkeypatch, repo, tmp_path)
    repo.create(PackageBuildRequest())

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


def test_list_deployment_package_audit_events_filters(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTaskRepository()
    audit_repo = _set_repo(monkeypatch, repo, tmp_path)
    audit_repo.record(action="package.create", status="accepted", target_id="task-1")
    audit_repo.record(action="package.create.blocked", status="blocked", target_id="task-2")
    audit_repo.record(action="package.download", status="completed", target_id="pkg-1")

    blocked = _client().get("/api/deployment-packages/audit-events?status=blocked")
    package_creates = _client().get("/api/deployment-packages/audit-events?actionPrefix=package.create")
    downloads = _client().get("/api/deployment-packages/audit-events?action=package.download&limit=1")

    assert blocked.status_code == 200, blocked.text
    assert [item["action"] for item in blocked.json()] == ["package.create.blocked"]
    assert package_creates.status_code == 200, package_creates.text
    assert {item["action"] for item in package_creates.json()} == {"package.create", "package.create.blocked"}
    assert downloads.status_code == 200, downloads.text
    assert [item["action"] for item in downloads.json()] == ["package.download"]


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(deployment_packages.router)
    app.include_router(downloads.router)
    return app


def _set_repo(monkeypatch: pytest.MonkeyPatch, repo: InMemoryTaskRepository, output_dir) -> InMemoryAuditEventRepository:
    audit_repo = InMemoryAuditEventRepository()
    monkeypatch.setattr(_common, "_TASK_REPO", repo)
    monkeypatch.setattr(_common, "_AUDIT_REPO", audit_repo)
    monkeypatch.setattr(
        _common,
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


def _microservice_result(delivery: dict[str, object] | None = None) -> MicroserviceScaffoldResult:
    return MicroserviceScaffoldResult(
        projectId="svc-test",
        serviceKey="asset-service",
        serviceName="Asset Service",
        projectKind="backend",
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
        image="registry.local/business/asset-service:prod",
        delivery=delivery or _delivery("success"),
        generatedFiles=[],
    )


def _delivery(status: str) -> dict[str, object]:
    return {
        "status": status,
        "steps": [],
        "build": {
            "status": status,
            "result": "SUCCESS" if status == "success" else status.upper(),
            "building": status == "running",
            "url": "http://jenkins/job/asset-service/1",
            "number": 1,
        },
    }


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
        ("192.168.10.210/k8s-platform/docker.elastic.co/elasticsearch/elasticsearch:8.17.4", "camunda-es"),
        ("192.168.10.210/local-ai/apache/iotdb:latest", "iotdb"),
        ("192.168.10.210/local-ai/prometheus:latest", "prometheus"),
    ]

    if seed_business:
        repo = InMemoryBusinessPlatformRepository()
        for item in registered:
            repo.upsert_registered(item)
        monkeypatch.setattr(_common, "_BUSINESS_PLATFORM_REPO", repo)

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
    monkeypatch.setattr(
        builder,
        "read_kubernetes_pods",
        lambda namespace, token=None: {
            "items": [
                {
                    "metadata": {"name": "eam-0", "labels": {"app.kubernetes.io/name": "eam"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "eam",
                                "envFrom": [{"secretRef": {"name": "local-ai-secrets"}}],
                                "env": [
                                    {"name": "DATABASE_URL", "value": "postgresql://eam_user:source-db-password@postgres:5432/local_ai?currentSchema=eam"},
                                    {"name": "MINIO_BUCKET", "value": "eam-docs"},
                                ],
                            }
                        ]
                    },
                }
            ]
        },
    )
    monkeypatch.setattr(builder, "read_kubernetes_secret", lambda namespace, name: {"DATABASE_PASSWORD": "source-db-password"})
    monkeypatch.setattr(builder, "read_kubernetes_configmap", lambda namespace, name: {})


def _wait_for_task(client: TestClient, task_id: str, headers: dict[str, str] | None = None) -> dict:
    for _ in range(50):
        response = client.get(f"/api/deployment-packages/tasks/{task_id}", headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in {"completed", "failed", "canceled"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Task {task_id} did not finish")
