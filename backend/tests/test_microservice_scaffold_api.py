from __future__ import annotations

import tarfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from deployment_package_factory.api import deployment_packages, microservices
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import RegisteredBusinessPlatform
from fakes import InMemoryBusinessPlatformRepository, InMemoryMicroserviceRepository


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(microservices.router)
    return TestClient(app)


def test_register_microservice_requires_registered_business_platform(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        deployment_packages,
        "_BUSINESS_PLATFORM_REPO",
        InMemoryBusinessPlatformRepository(),
    )
    monkeypatch.setattr(deployment_packages, "_MICROSERVICE_REPO", InMemoryMicroserviceRepository())

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
    repo = InMemoryBusinessPlatformRepository()
    microservice_repo = InMemoryMicroserviceRepository()
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
    assert payload["validation"]["passed"] is True
    assert payload["validation"]["fileCount"] == len(payload["generatedFiles"])
    assert {item["name"] for item in payload["validation"]["checks"]} == {"required-files", "python-syntax", "pipeline-files", "middleware-placeholders", "artifact-archive"}
    artifact = Path(payload["artifactPath"])
    assert artifact.exists()

    with tarfile.open(artifact, "r:gz") as tar:
        names = set(tar.getnames())
        assert "asset-service/README.md" in names
        assert "asset-service/Dockerfile" in names
        assert "asset-service/Jenkinsfile" in names
        assert "asset-service/.env.template" in names
        assert "asset-service/config/middleware.example.yaml" in names
        assert "asset-service/deploy.sh" in names
        assert "asset-service/migrate.sh" in names
        assert "asset-service/run-local.sh" in names
        assert "asset-service/test.sh" in names
        assert "asset-service/src/app/main.py" in names
        assert "asset-service/src/app/domain/models.py" in names
        assert "asset-service/src/app/application/use_cases.py" in names
        assert "asset-service/src/app/infrastructure/redis_client.py" in names
        assert "asset-service/src/app/infrastructure/postgres_repository.py" in names
        assert "asset-service/src/app/interfaces/http/routes.py" in names
        assert "asset-service/tests/test_api.py" in names
        assert "asset-service/deploy/k8s/namespace.yaml" in names
        assert "asset-service/deploy/k8s/deployment.yaml" in names
        assert "asset-service/deploy/k8s/ingress.template.yaml" in names
        assert "asset-service/deploy/helm/asset-service/Chart.yaml" in names
        assert "asset-service/deploy/helm/asset-service/values.yaml" in names
        assert "asset-service/deploy/helm/asset-service/templates/deployment.yaml" in names
        readme = tar.extractfile("asset-service/README.md").read().decode("utf-8")
        dockerfile = tar.extractfile("asset-service/Dockerfile").read().decode("utf-8")
        env_template = tar.extractfile("asset-service/.env.template").read().decode("utf-8")
        jenkinsfile = tar.extractfile("asset-service/Jenkinsfile").read().decode("utf-8")
        deploy_sh = tar.extractfile("asset-service/deploy.sh").read().decode("utf-8")
        deployment = tar.extractfile("asset-service/deploy/k8s/deployment.yaml").read().decode("utf-8")
        helm_values = tar.extractfile("asset-service/deploy/helm/asset-service/values.yaml").read().decode("utf-8")
        routes = tar.extractfile("asset-service/src/app/interfaces/http/routes.py").read().decode("utf-8")
        python_sources = {
            name: tar.extractfile(name).read().decode("utf-8")
            for name in names
            if name.startswith("asset-service/src/app/") and name.endswith(".py")
        }

    assert "Platform: EAM (eam)" in readme
    assert "domain/" in readme
    assert "application/" in readme
    assert "infrastructure/" in readme
    assert "interfaces/http/" in readme
    assert "curl -X POST http://127.0.0.1:8000/api/v1/items/demo-item" in readme
    assert "USER 10001" in dockerfile
    assert "BUSINESS_PLATFORM_KEY=eam" in env_template
    assert "BUSINESS_PLATFORM_NAMESPACE=test-biz-eam-4x60" in env_template
    assert "./deploy.sh $IMAGE" in jenkinsfile
    assert "helm upgrade --install" in deploy_sh
    assert "helm upgrade --install asset-service deploy/helm/asset-service" in readme
    assert "business-platform: eam" in deployment
    assert "resources:" in deployment
    assert "livenessProbe:" in deployment
    assert "repository: registry.local/business/asset-service" in helm_values
    assert 'router = APIRouter(prefix="/api/v1")' in routes
    assert "create_demo_item" in routes
    for name, source in python_sources.items():
        compile(source, name, "exec")

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


def test_microservice_options_include_multi_stack_and_middleware() -> None:
    response = _client().get("/api/microservices/options")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert {item["key"] for item in payload["projectKinds"]} == {"backend", "frontend", "microfrontend"}
    assert {"nodejs-express", "java-spring-cloud-alibaba", "vue3-vite", "react-vite", "qiankun", "wujie"}.issubset(
        {item["key"] for item in payload["techStacks"]}
    )
    assert {"redis", "dm", "postgresql", "iotdb", "mongodb", "kafka", "mq"}.issubset({item["key"] for item in payload["middleware"]})


def test_register_microservice_generates_nodejs_project_with_extended_middleware(tmp_path, monkeypatch) -> None:
    _register_platform(tmp_path, monkeypatch)

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-node",
            "serviceName": "Asset Node",
            "projectKind": "backend",
            "techStack": "nodejs-express",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
            "middleware": ["redis", "mongodb", "kafka", "mq"],
            "imageRegistry": "registry.local",
            "imageNamespace": "business",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["validation"]["passed"] is True
    assert {item["name"] for item in payload["validation"]["checks"]} == {"required-files", "pipeline-files", "middleware-placeholders", "artifact-archive"}
    with tarfile.open(Path(payload["artifactPath"]), "r:gz") as tar:
        names = set(tar.getnames())
        assert "asset-node/src/domain/demo.ts" in names
        assert "asset-node/src/application/useCases.ts" in names
        assert "asset-node/src/interfaces/http/server.ts" in names
        env_template = tar.extractfile("asset-node/.env.template").read().decode("utf-8")
        middleware_yaml = tar.extractfile("asset-node/config/middleware.example.yaml").read().decode("utf-8")
    assert "MONGODB_ENDPOINT=__REPLACE_WITH_MONGODB_ENDPOINT__" in env_template
    assert "kafka:" in middleware_yaml
    assert "mq:" in middleware_yaml


def test_register_microservice_generates_java_and_frontend_projects(tmp_path, monkeypatch) -> None:
    _register_platform(tmp_path, monkeypatch)

    java_response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-java",
            "serviceName": "Asset Java",
            "projectKind": "backend",
            "techStack": "java-spring-cloud-alibaba",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
            "middleware": ["dm", "iotdb"],
            "imageRegistry": "registry.local",
            "imageNamespace": "business",
        },
    )
    vue_response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-ui",
            "serviceName": "Asset UI",
            "projectKind": "frontend",
            "techStack": "vue3-vite",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
            "middleware": [],
            "imageRegistry": "registry.local",
            "imageNamespace": "business",
        },
    )

    assert java_response.status_code == 200, java_response.text
    assert vue_response.status_code == 200, vue_response.text
    with tarfile.open(Path(java_response.json()["artifactPath"]), "r:gz") as tar:
        names = set(tar.getnames())
        assert "asset-java/pom.xml" in names
        assert "asset-java/src/main/java/com/example/domain/DemoItem.java" in names
        assert "asset-java/src/main/resources/application.yml" in names
    with tarfile.open(Path(vue_response.json()["artifactPath"]), "r:gz") as tar:
        names = set(tar.getnames())
        assert "asset-ui/package.json" in names
        assert "asset-ui/src/main.ts" in names
        assert "asset-ui/src/router/index.ts" in names


def test_register_microservice_accepts_runtime_discovered_business_platform(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path))
    repo = InMemoryBusinessPlatformRepository()
    microservice_repo = InMemoryMicroserviceRepository()
    monkeypatch.setattr(deployment_packages, "_BUSINESS_PLATFORM_REPO", repo)
    monkeypatch.setattr(deployment_packages, "_MICROSERVICE_REPO", microservice_repo)
    monkeypatch.setattr(
        deployment_packages,
        "list_registered_business_platforms",
        lambda include_disabled=False: [
            RegisteredBusinessPlatform(
                key="eam",
                name="Test EAM 4x60",
                profile="4x60",
                namespace="test-biz-eam-4x60",
                source_env="test",
                status="active",
            )
        ],
    )

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "mes-service",
            "serviceName": "生产制造执行系统",
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
    assert payload["businessPlatformName"] == "Test EAM 4x60"
    assert payload["businessPlatformNamespace"] == "test-biz-eam-4x60"
    assert repo.resolve("test", "eam", "4x60").namespace == "test-biz-eam-4x60"


def test_register_microservice_accepts_numeric_prefix_service_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path))
    repo = InMemoryBusinessPlatformRepository()
    microservice_repo = InMemoryMicroserviceRepository()
    monkeypatch.setattr(deployment_packages, "_BUSINESS_PLATFORM_REPO", repo)
    monkeypatch.setattr(deployment_packages, "_MICROSERVICE_REPO", microservice_repo)
    repo.upsert_registered(
        RegisteredBusinessPlatform(
            key="eam",
            name="EAM",
            profile="4x60",
            namespace="test-biz-eam-4x60",
            source_env="test",
            status="active",
        ),
    )

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "460mes-service",
            "serviceName": "460Mes服务",
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
    assert payload["serviceKey"] == "460mes-service"
    assert payload["cloneCommand"].endswith("&& cd 460mes-service")
    registered = microservice_repo.get("test", "eam", "4x60", "460mes-service")
    assert registered is not None
    assert registered["image"] == "registry.local/business/460mes-service"


def test_register_microservice_normalizes_scaffold_inputs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path))
    repo = InMemoryBusinessPlatformRepository()
    microservice_repo = InMemoryMicroserviceRepository()
    monkeypatch.setattr(deployment_packages, "_BUSINESS_PLATFORM_REPO", repo)
    monkeypatch.setattr(deployment_packages, "_MICROSERVICE_REPO", microservice_repo)
    repo.upsert_registered(
        RegisteredBusinessPlatform(
            key="eam",
            name="EAM",
            profile="4x60",
            namespace="test-biz-eam-4x60",
            source_env="test",
            status="active",
        ),
    )

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "  EAM-Asset-Service  ",
            "serviceName": "资产服务",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
            "gitGroup": " /Business-Services/EAM/ ",
            "imageRegistry": " registry.local:5000/ ",
            "imageNamespace": " /Business/EAM/ ",
            "k8sNamespace": " Test-Biz-EAM-Asset ",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["serviceKey"] == "eam-asset-service"
    registered = microservice_repo.get("test", "eam", "4x60", "eam-asset-service")
    assert registered is not None
    assert registered["gitGroup"] == "business-services/eam"
    assert registered["image"] == "registry.local:5000/business/eam/eam-asset-service"
    assert registered["k8sNamespace"] == "test-biz-eam-asset"


def test_register_microservice_rejects_registry_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(deployment_packages, "_BUSINESS_PLATFORM_REPO", InMemoryBusinessPlatformRepository())
    monkeypatch.setattr(deployment_packages, "_MICROSERVICE_REPO", InMemoryMicroserviceRepository())

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-service",
            "serviceName": "资产服务",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "imageRegistry": "registry.local/business",
        },
    )

    assert response.status_code == 422
    assert "imageRegistry must be a registry host" in response.text


def test_register_microservice_rejects_invalid_port(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(deployment_packages, "_BUSINESS_PLATFORM_REPO", InMemoryBusinessPlatformRepository())
    monkeypatch.setattr(deployment_packages, "_MICROSERVICE_REPO", InMemoryMicroserviceRepository())

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-service",
            "serviceName": "资产服务",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "port": 70000,
        },
    )

    assert response.status_code == 422
    assert "port must be between 1 and 65535" in response.text


def _register_platform(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path))
    repo = InMemoryBusinessPlatformRepository()
    microservice_repo = InMemoryMicroserviceRepository()
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
