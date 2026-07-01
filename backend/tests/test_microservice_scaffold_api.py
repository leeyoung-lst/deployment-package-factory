from __future__ import annotations

import tarfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from deployment_package_factory.api import deployment_packages, microservices
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import RegisteredBusinessPlatform
from deployment_package_factory.services.settings import GitSettings, HarborSettings, JenkinsSettings, SystemSettings
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
    assert payload["image"] == "registry.local/business/asset-service"
    assert payload["buildCommand"] == "./build.sh registry.local/business/asset-service:dev"
    assert payload["deployCommand"] == "./deploy.sh registry.local/business/asset-service:dev"
    assert payload["gitRepositoryUrl"] == "business-services/asset-service"
    assert payload["jenkinsJob"] == "business-services/asset-service"
    assert payload["validation"]["passed"] is True
    assert payload["validation"]["fileCount"] == len(payload["generatedFiles"])
    assert {item["name"] for item in payload["validation"]["checks"]} == {
        "required-files",
        "python-syntax",
        "pipeline-files",
        "helm-templates",
        "tech-stack-contract",
        "middleware-placeholders",
        "artifact-archive",
    }
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
    assert "withCredentials" in jenkinsfile
    assert "dpf-registry-credentials" in jenkinsfile
    assert "dpf-kubeconfig" in jenkinsfile
    assert 'docker login "$IMAGE_REGISTRY"' in jenkinsfile
    assert 'KUBECONFIG="$KUBECONFIG_FILE" ./deploy.sh "$IMAGE"' in jenkinsfile
    assert "REDIS_URL=redis://redis.test-middleware-public.svc.cluster.local:6379/0" in env_template
    assert "POSTGRES_DSN=postgresql://app:__REPLACE_WITH_POSTGRES_PASSWORD__@postgres.test-middleware-public.svc.cluster.local:5432/app" in env_template
    assert "REDIS_URL: redis://redis.test-middleware-public.svc.cluster.local:6379/0" in helm_values
    assert "POSTGRES_DSN: postgresql://app:__REPLACE_WITH_POSTGRES_PASSWORD__@postgres.test-middleware-public.svc.cluster.local:5432/app" in helm_values
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
    assert services[0]["buildCommand"] == "./build.sh registry.local/business/asset-service:dev"
    assert services[0]["deployCommand"] == "./deploy.sh registry.local/business/asset-service:dev"
    assert services[0]["jenkinsJob"] == "business-services/asset-service"

    app = FastAPI()
    app.include_router(deployment_packages.router)
    options = TestClient(app).get("/api/deployment-packages/options")

    assert options.status_code == 200, options.text
    assert options.json()["microservices"][0]["serviceKey"] == "asset-service"


def test_microservice_options_include_multi_stack_and_middleware() -> None:
    response = _client().get("/api/microservices/options")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert {item["key"] for item in payload["projectKinds"]} == {"backend", "frontend"}
    assert {"nodejs-express", "java-spring-cloud-alibaba", "vue3-vite", "react-vite"}.issubset(
        {item["key"] for item in payload["techStacks"]}
    )
    assert {"qiankun", "wujie"} == {item["key"] for item in payload["microFrontendFrameworks"]}
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
    assert {item["name"] for item in payload["validation"]["checks"]} == {
        "required-files",
        "pipeline-files",
        "helm-templates",
        "tech-stack-contract",
        "middleware-placeholders",
        "artifact-archive",
    }
    with tarfile.open(Path(payload["artifactPath"]), "r:gz") as tar:
        names = set(tar.getnames())
        assert "asset-node/src/domain/demo.ts" in names
        assert "asset-node/src/domain/services.ts" in names
        assert "asset-node/src/application/useCases.ts" in names
        assert "asset-node/src/config/settings.ts" in names
        assert "asset-node/src/infrastructure/logger.ts" in names
        assert "asset-node/src/infrastructure/middlewareClients.ts" in names
        assert "asset-node/src/interfaces/http/routes.ts" in names
        assert "asset-node/src/interfaces/http/server.ts" in names
        assert "asset-node/tests/demo.test.ts" in names
        package_json = tar.extractfile("asset-node/package.json").read().decode("utf-8")
        tsconfig = tar.extractfile("asset-node/tsconfig.json").read().decode("utf-8")
        env_template = tar.extractfile("asset-node/.env.template").read().decode("utf-8")
        middleware_yaml = tar.extractfile("asset-node/config/middleware.example.yaml").read().decode("utf-8")
        helm_deployment = tar.extractfile("asset-node/deploy/helm/asset-node/templates/deployment.yaml").read().decode("utf-8")
        helm_configmap = tar.extractfile("asset-node/deploy/helm/asset-node/templates/configmap.yaml").read().decode("utf-8")
        helm_secret = tar.extractfile("asset-node/deploy/helm/asset-node/templates/secret.yaml").read().decode("utf-8")
    assert '"test":"node --test dist/tests/*.test.js"' in package_json
    assert '"start":"node dist/src/interfaces/http/server.js"' in package_json
    assert '"include":["src","tests"]' in tsconfig
    assert "MONGODB_ENDPOINT=mongodb://mongodb.test-middleware-public.svc.cluster.local:27017/app" in env_template
    assert "REDIS_ENDPOINT=redis://redis.test-middleware-public.svc.cluster.local:6379/0" in env_template
    assert "kafka:" in middleware_yaml
    assert "mq:" in middleware_yaml
    assert "envFrom:" in helm_deployment
    assert "name: asset-node-config" in helm_configmap
    assert "name: asset-node-secret" in helm_secret
    assert 'include "asset-node.name"' not in helm_configmap
    assert 'include "asset-node.name"' not in helm_secret


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
        pom = tar.extractfile("asset-java/pom.xml").read().decode("utf-8")
        dockerfile = tar.extractfile("asset-java/Dockerfile").read().decode("utf-8")
        env_template = tar.extractfile("asset-java/.env.template").read().decode("utf-8")
        assert "asset-java/pom.xml" in names
        assert "asset-java/src/main/java/com/example/domain/DemoItem.java" in names
        assert "asset-java/src/main/resources/application.yml" in names
        assert "<java.version>17</java.version>" in pom
        assert "<maven.compiler.release>${java.version}</maven.compiler.release>" in pom
        assert "<artifactId>maven-compiler-plugin</artifactId>" in pom
        assert "<project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>" in pom
        assert "eclipse-temurin:17-jre" in dockerfile
        assert "NACOS_ENDPOINT=nacos.test-middleware-public.svc.cluster.local:8848" in env_template
    with tarfile.open(Path(vue_response.json()["artifactPath"]), "r:gz") as tar:
        names = set(tar.getnames())
        assert "asset-ui/package.json" in names
        assert "asset-ui/vite.config.ts" in names
        assert "asset-ui/tsconfig.json" in names
        assert "asset-ui/src/main.ts" in names
        assert "asset-ui/src/router/index.ts" in names


def test_register_microservice_generates_react_frontend_project(tmp_path, monkeypatch) -> None:
    _register_platform(tmp_path, monkeypatch)

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-react",
            "serviceName": "Asset React",
            "projectKind": "frontend",
            "techStack": "react-vite",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
            "imageRegistry": "registry.local",
            "imageNamespace": "business",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["validation"]["passed"] is True
    with tarfile.open(Path(payload["artifactPath"]), "r:gz") as tar:
        names = set(tar.getnames())
        package_json = tar.extractfile("asset-react/package.json").read().decode("utf-8")
        vite_config = tar.extractfile("asset-react/vite.config.ts").read().decode("utf-8")
    assert "asset-react/src/main.tsx" in names
    assert "asset-react/src/router/index.ts" not in names
    assert '"antd"' in package_json
    assert "@vitejs/plugin-react" in vite_config


def test_register_frontend_microservice_can_enable_micro_frontend_framework(tmp_path, monkeypatch) -> None:
    _register_platform(tmp_path, monkeypatch)

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-portal",
            "serviceName": "Asset Portal",
            "projectKind": "frontend",
            "techStack": "vue3-vite",
            "microFrontendFramework": "qiankun",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
            "imageRegistry": "registry.local",
            "imageNamespace": "business",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["microFrontendFramework"] == "qiankun"
    assert payload["validation"]["passed"] is True
    with tarfile.open(Path(payload["artifactPath"]), "r:gz") as tar:
        package_json = tar.extractfile("asset-portal/package.json").read().decode("utf-8")
    assert '"qiankun":"^2.10.16"' in package_json


def test_register_react_frontend_uses_react_wujie_adapter(tmp_path, monkeypatch) -> None:
    _register_platform(tmp_path, monkeypatch)

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-wujie",
            "serviceName": "Asset Wujie",
            "projectKind": "frontend",
            "techStack": "react-vite",
            "microFrontendFramework": "wujie",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
            "imageRegistry": "registry.local",
            "imageNamespace": "business",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["validation"]["passed"] is True
    with tarfile.open(Path(payload["artifactPath"]), "r:gz") as tar:
        package_json = tar.extractfile("asset-wujie/package.json").read().decode("utf-8")
    assert '"wujie-react":"^1.0.5"' in package_json
    assert "wujie-vue3" not in package_json


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
    assert registered["k8sNamespace"] == "test-biz-eam-4x60"


def test_register_microservice_uses_system_setting_defaults(tmp_path, monkeypatch) -> None:
    _register_platform(tmp_path, monkeypatch)
    monkeypatch.setattr(
        microservices,
        "_system_settings",
        lambda: SystemSettings(
            git=GitSettings(baseUrl="https://git.local/scm", group="factory-services"),
            harbor=HarborSettings(registry="harbor.local:8443", project="factory"),
            jenkins=JenkinsSettings(baseUrl="https://jenkins.local", folder="factory-services"),
        ),
    )

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-defaults",
            "serviceName": "资产默认配置服务",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
            "gitGroup": "",
            "imageRegistry": "",
            "imageNamespace": "",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["gitRepositoryUrl"] == "https://git.local/scm/factory-services/asset-defaults.git"
    assert payload["image"] == "harbor.local:8443/factory/asset-defaults"
    assert payload["jenkinsJob"] == "https://jenkins.local/job/factory-services/job/asset-defaults"
    assert payload["delivery"]["status"] == "pending"
    assert {step["name"]: step["status"] for step in payload["delivery"]["steps"]} == {
        "git-project": "pending",
        "jenkins-job": "pending",
    }
    git_step = next(step for step in payload["delivery"]["steps"] if step["name"] == "git-project")
    assert git_step["phase"] == "config"
    assert git_step["retryable"] is True
    assert git_step["elapsedMs"] >= 0
    assert "Token" in git_step["hint"]


def test_register_microservice_prepares_git_and_jenkins_when_credentials_exist(tmp_path, monkeypatch) -> None:
    _register_platform(tmp_path, monkeypatch)
    calls: list[tuple[str, str]] = []

    class FakeGitLabClient:
        def __init__(self, base_url: str, token: str) -> None:
            calls.append(("git-init", f"{base_url}:{token}"))

        def ensure_project(self, group: str, service_key: str) -> str:
            calls.append(("git-project", f"{group}/{service_key}"))
            return f"https://git.local/scm/{group}/{service_key}.git"

    class FakeJenkinsClient:
        def __init__(self, base_url: str, username: str, token: str) -> None:
            calls.append(("jenkins-init", f"{base_url}:{username}:{token}"))

        def ensure_pipeline_job(self, folder: str, service_key: str, git_url: str) -> None:
            calls.append(("jenkins-job", f"{folder}/{service_key}:{git_url}"))
            return f"/job/{folder}/job/{service_key}"

        def trigger_build(self, job_path: str) -> str:
            calls.append(("jenkins-build", job_path))
            return f"https://jenkins.local{job_path}/build"

    monkeypatch.setattr(microservices, "_system_settings", lambda: SystemSettings(
        git=GitSettings(baseUrl="https://git.local/scm", group="factory-services", token="git-token"),
        harbor=HarborSettings(registry="harbor.local:8443", project="factory"),
        jenkins=JenkinsSettings(baseUrl="https://jenkins.local", folder="factory-services", username="admin", password="jenkins-token"),
    ))
    monkeypatch.setattr("deployment_package_factory.services.microservices.git_providers.GitLabClient", FakeGitLabClient)
    monkeypatch.setattr("deployment_package_factory.services.microservices.delivery.JenkinsClient", FakeJenkinsClient)
    monkeypatch.setattr("deployment_package_factory.services.microservices.delivery._push_initial_commit", lambda *args, **kwargs: calls.append(("git-push", f"{args[1]}:{args[3]}")))

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-auto",
            "serviceName": "资产自动交付服务",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["delivery"]["status"] == "ready"
    assert {step["name"]: step["status"] for step in payload["delivery"]["steps"]} == {
        "git-project": "ready",
        "jenkins-job": "ready",
    }
    assert all(step["phase"] == "provision" for step in payload["delivery"]["steps"])
    assert all(step["retryable"] is False for step in payload["delivery"]["steps"])
    assert ("git-project", "factory-services/asset-auto") in calls
    assert ("git-push", "https://git.local/scm/factory-services/asset-auto.git:oauth2") in calls
    assert any(item[0] == "jenkins-job" and "asset-auto" in item[1] for item in calls)
    assert ("jenkins-build", "/job/factory-services/job/asset-auto") in calls


def test_register_microservice_prepares_github_project_when_provider_configured(tmp_path, monkeypatch) -> None:
    _register_platform(tmp_path, monkeypatch)
    calls: list[tuple[str, str]] = []

    class FakeGitHubClient:
        def __init__(self, base_url: str, token: str) -> None:
            calls.append(("github-init", f"{base_url}:{token}"))

        def ensure_project(self, owner: str, service_key: str) -> str:
            calls.append(("github-project", f"{owner}/{service_key}"))
            return f"https://github.com/{owner}/{service_key}.git"

    class FakeJenkinsClient:
        def __init__(self, base_url: str, username: str, token: str) -> None:
            pass

        def ensure_pipeline_job(self, folder: str, service_key: str, git_url: str) -> str:
            calls.append(("jenkins-job", f"{folder}/{service_key}:{git_url}"))
            return f"/job/{folder}/job/{service_key}"

        def trigger_build(self, job_path: str) -> str:
            return f"https://jenkins.local{job_path}/build"

    monkeypatch.setattr(microservices, "_system_settings", lambda: SystemSettings(
        git=GitSettings(provider="github", baseUrl="https://github.com", group="sajidsah565-sys", token="github-token"),
        harbor=HarborSettings(registry="harbor.local:8443", project="factory"),
        jenkins=JenkinsSettings(baseUrl="https://jenkins.local", folder="factory-services", username="admin", password="jenkins-token"),
    ))
    monkeypatch.setattr("deployment_package_factory.services.microservices.git_providers.GitHubClient", FakeGitHubClient)
    monkeypatch.setattr("deployment_package_factory.services.microservices.delivery.JenkinsClient", FakeJenkinsClient)
    monkeypatch.setattr("deployment_package_factory.services.microservices.delivery._push_initial_commit", lambda *args, **kwargs: calls.append(("git-push", f"{args[1]}:{args[3]}")))

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-github",
            "serviceName": "资产 GitHub 服务",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["delivery"]["status"] == "ready"
    assert payload["gitRepositoryUrl"] == "https://github.com/sajidsah565-sys/asset-github.git"
    assert ("github-project", "sajidsah565-sys/asset-github") in calls
    assert ("git-push", "https://github.com/sajidsah565-sys/asset-github.git:x-access-token") in calls


def test_retry_microservice_delivery_updates_registered_record(tmp_path, monkeypatch) -> None:
    _register_platform(tmp_path, monkeypatch)
    calls: list[tuple[str, str]] = []

    class FakeGitLabClient:
        def __init__(self, base_url: str, token: str) -> None:
            pass

        def ensure_project(self, group: str, service_key: str) -> str:
            calls.append(("git-project", service_key))
            return f"https://git.local/scm/{group}/{service_key}.git"

    class FakeJenkinsClient:
        def __init__(self, base_url: str, username: str, token: str) -> None:
            pass

        def ensure_pipeline_job(self, folder: str, service_key: str, git_url: str) -> str:
            calls.append(("jenkins-job", service_key))
            return f"/job/{folder}/job/{service_key}"

        def trigger_build(self, job_path: str) -> str:
            calls.append(("jenkins-build", job_path))
            return f"https://jenkins.local{job_path}/build"

    monkeypatch.setattr(
        microservices,
        "_system_settings",
        lambda: SystemSettings(
            git=GitSettings(baseUrl="https://git.local/scm", group="factory-services", token="git-token"),
            harbor=HarborSettings(registry="harbor.local:8443", project="factory"),
            jenkins=JenkinsSettings(baseUrl="https://jenkins.local", folder="factory-services", username="admin", password="jenkins-token"),
        ),
    )
    monkeypatch.setattr("deployment_package_factory.services.microservices.git_providers.GitLabClient", FakeGitLabClient)
    monkeypatch.setattr("deployment_package_factory.services.microservices.delivery.JenkinsClient", FakeJenkinsClient)
    monkeypatch.setattr("deployment_package_factory.services.microservices.delivery._push_initial_commit", lambda *args, **kwargs: None)

    client = _client()
    created = client.post(
        "/api/microservices",
        json={
            "serviceKey": "asset-retry",
            "serviceName": "资产重试服务",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
        },
    )

    assert created.status_code == 200, created.text
    project_id = created.json()["projectId"]
    calls.clear()

    retried = client.post(f"/api/microservices/{project_id}/delivery/retry")

    assert retried.status_code == 200, retried.text
    payload = retried.json()
    assert payload["delivery"]["status"] == "ready"
    assert payload["microservice"]["delivery"]["status"] == "ready"
    assert ("git-project", "asset-retry") in calls
    assert ("jenkins-build", "/job/factory-services/job/asset-retry") in calls


def test_get_microservice_delivery_status_refreshes_jenkins_build(tmp_path, monkeypatch) -> None:
    _register_platform(tmp_path, monkeypatch)

    class FakeGitLabClient:
        def __init__(self, base_url: str, token: str) -> None:
            pass

        def ensure_project(self, group: str, service_key: str) -> str:
            return f"https://git.local/scm/{group}/{service_key}.git"

    class FakeJenkinsClient:
        def __init__(self, base_url: str, username: str, token: str) -> None:
            pass

        def ensure_pipeline_job(self, folder: str, service_key: str, git_url: str) -> str:
            return f"/job/{folder}/job/{service_key}"

        def trigger_build(self, job_path: str) -> str:
            return f"https://jenkins.local{job_path}/1"

        def read_build_status(self, build_url: str) -> dict[str, object]:
            return {"status": "success", "result": "success", "building": False, "url": build_url, "number": 1, "message": "Jenkins 构建成功。"}

    monkeypatch.setattr(
        microservices,
        "_system_settings",
        lambda: SystemSettings(
            git=GitSettings(baseUrl="https://git.local/scm", group="factory-services", token="git-token"),
            harbor=HarborSettings(registry="harbor.local:8443", project="factory"),
            jenkins=JenkinsSettings(baseUrl="https://jenkins.local", folder="factory-services", username="admin", password="jenkins-token"),
        ),
    )
    monkeypatch.setattr("deployment_package_factory.services.microservices.git_providers.GitLabClient", FakeGitLabClient)
    monkeypatch.setattr("deployment_package_factory.services.microservices.delivery.JenkinsClient", FakeJenkinsClient)
    monkeypatch.setattr("deployment_package_factory.services.microservices.delivery._push_initial_commit", lambda *args, **kwargs: None)

    client = _client()
    created = client.post(
        "/api/microservices",
        json={
            "serviceKey": "asset-status",
            "serviceName": "资产状态服务",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
            "businessPlatformProfile": "4x60",
        },
    )

    assert created.status_code == 200, created.text
    project_id = created.json()["projectId"]
    refreshed = client.get(f"/api/microservices/{project_id}/delivery/status")

    assert refreshed.status_code == 200, refreshed.text
    payload = refreshed.json()
    assert payload["delivery"]["status"] == "success"
    assert payload["delivery"]["build"]["status"] == "success"
    assert payload["microservice"]["delivery"]["build"]["number"] == 1


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


def test_register_microservice_rejects_micro_frontend_framework_for_backend(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(deployment_packages, "_BUSINESS_PLATFORM_REPO", InMemoryBusinessPlatformRepository())
    monkeypatch.setattr(deployment_packages, "_MICROSERVICE_REPO", InMemoryMicroserviceRepository())

    response = _client().post(
        "/api/microservices",
        json={
            "serviceKey": "asset-service",
            "serviceName": "资产服务",
            "projectKind": "backend",
            "techStack": "python-fastapi",
            "microFrontendFramework": "qiankun",
            "sourceEnv": "test",
            "businessPlatformKey": "eam",
        },
    )

    assert response.status_code == 422
    assert "microFrontendFramework can only be used by frontend projectKind" in response.text


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
