from __future__ import annotations

from deployment_package_factory.services.deployment_packages.deployment_renderer import render_deployment_files


def test_render_deployment_files_declares_expected_paths_and_executable_flags() -> None:
    files = render_deployment_files(_manifest())
    by_path = {item.path.as_posix(): item for item in files}

    assert "k8s/namespaces.yaml" in by_path
    assert "k8s/kustomization.yaml" in by_path
    assert "k8s/layers/00-platform/kustomization.yaml" in by_path
    assert "k8s/layers/10-data/kustomization.yaml" in by_path
    assert "k8s/layers/60-apps/kustomization.yaml" in by_path
    assert "k8s/install.sh" in by_path
    assert "docker-compose/docker-compose.yml" in by_path
    assert "docker-compose/.env" in by_path
    assert "docker-compose/dry-run.sh" in by_path
    assert "scripts/secret-check.sh" in by_path
    assert "scripts/diagnostics.sh" in by_path
    assert "scripts/diagnostics.ps1" in by_path
    assert not by_path["k8s/namespaces.yaml"].executable
    assert not by_path["docker-compose/docker-compose.yml"].executable
    assert by_path["k8s/install.sh"].executable
    assert by_path["docker-compose/dry-run.sh"].executable
    assert by_path["scripts/secret-check.sh"].executable
    assert by_path["scripts/diagnostics.sh"].executable
    assert not by_path["scripts/diagnostics.ps1"].executable


def test_render_deployment_files_includes_namespaces_registry_and_secret_modes() -> None:
    files = render_deployment_files(_manifest())
    by_path = {item.path.as_posix(): item.content for item in files}

    assert "name: prod-base-public" in by_path["k8s/namespaces.yaml"]
    assert "name: prod-business-eam" in by_path["k8s/namespaces.yaml"]
    assert "harbor.example.com/prod/local-ai-eam-service:prod" in by_path["k8s/deployments.yaml"]
    assert "layers/00-platform" in by_path["k8s/kustomization.yaml"]
    assert "layers/10-data" in by_path["k8s/kustomization.yaml"]
    assert "layers/60-apps" in by_path["k8s/kustomization.yaml"]
    assert "layers/30-edge" not in by_path["k8s/kustomization.yaml"]
    assert "layers/40-workflow-webui" not in by_path["k8s/kustomization.yaml"]
    assert "secrets.template.yaml" in by_path["k8s/layers/00-platform/kustomization.yaml"]
    assert "name: postgres" in by_path["k8s/layers/10-data/deployments.yaml"]
    assert "name: local-ai-eam-service" in by_path["k8s/layers/60-apps/deployments.yaml"]
    assert 'kubectl apply -k "${SCRIPT_DIR}/layers/00-platform"' in by_path["k8s/install.sh"]
    assert 'kubectl apply -k "${SCRIPT_DIR}/layers/10-data"' in by_path["k8s/install.sh"]
    assert 'kubectl apply -k "${SCRIPT_DIR}/layers/60-apps"' in by_path["k8s/install.sh"]
    assert by_path["k8s/install.sh"].find("layers/00-platform") < by_path["k8s/install.sh"].find("layers/10-data")
    assert by_path["k8s/install.sh"].find("layers/10-data") < by_path["k8s/install.sh"].find("layers/60-apps")
    assert "harbor.example.com/prod/postgres:16" in by_path["docker-compose/docker-compose.yml"]
    assert "DATABASE_PASSWORD=source-db-password" in by_path["docker-compose/.env"]
    assert "MINIO_ROOT_PASSWORD=source-minio-password" in by_path["docker-compose/.env"]
    assert "QDRANT_API_KEY=source-qdrant-key" in by_path["docker-compose/.env"]
    assert "__REPLACE_WITH_" not in by_path["docker-compose/.env"]
    assert "__REPLACE_WITH_DATABASE_PASSWORD__" in by_path["docker-compose/.env.template"]
    assert "__REPLACE_WITH_QDRANT_API_KEY__" in by_path["docker-compose/.env.template"]
    assert "DATABASE_PASSWORD: __REPLACE_WITH_DATABASE_PASSWORD__" in by_path["k8s/secrets.template.yaml"]
    assert "QDRANT_API_KEY: __REPLACE_WITH_QDRANT_API_KEY__" in by_path["k8s/secrets.template.yaml"]
    assert "POSTGRES_PASSWORD: ${DATABASE_PASSWORD}" in by_path["docker-compose/docker-compose.yml"]
    assert 'command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]' in by_path["docker-compose/docker-compose.yml"]
    assert 'test: ["CMD-SHELL", "pg_isready -U \\"$$POSTGRES_USER\\" -d \\"$$POSTGRES_DB\\""]' in by_path["docker-compose/docker-compose.yml"]
    assert 'test: ["CMD-SHELL", "redis-cli -a \\"$$REDIS_PASSWORD\\" ping"]' in by_path["docker-compose/docker-compose.yml"]
    assert "condition: service_healthy" in by_path["docker-compose/docker-compose.yml"]
    assert '      - "18181:8000"' in by_path["docker-compose/docker-compose.yml"]
    assert "containerPort: 8000" in by_path["k8s/deployments.yaml"]
    assert "name: init-scripts" in by_path["k8s/jobs/init-db.yaml"]
    assert "command: [\"/bin/sh\", \"/init/run-init.sh\"]" in by_path["k8s/jobs/init-db.yaml"]
    assert '"${PACKAGE_ROOT}/scripts/secret-check.sh" k8s' in by_path["k8s/install.sh"]
    assert '"${PACKAGE_ROOT}/scripts/secret-check.sh" docker-compose' in by_path["docker-compose/install.sh"]
    assert '"${PACKAGE_ROOT}/init/run-init.sh" all' in by_path["docker-compose/install.sh"]
    assert "check_disk_space" in by_path["scripts/check-prerequisites.sh"]
    assert "check_image_archives" in by_path["scripts/check-prerequisites.sh"]
    assert "Missing image archives" in by_path["scripts/check-prerequisites.sh"]
    assert "ps --format json" in by_path["scripts/health-check.sh"]
    assert "Unhealthy docker-compose services" in by_path["scripts/health-check.sh"]
    assert "Docker Compose service health check passed" in by_path["scripts/health-check.sh"]
    assert "Deployment diagnostics failed" in by_path["scripts/diagnostics.sh"]
    assert "COMPOSE_HTTP_CHECKS" in by_path["scripts/diagnostics.sh"]
    assert "Docker Compose diagnostics passed." in by_path["scripts/diagnostics.sh"]
    assert "K8s diagnostics passed." in by_path["scripts/diagnostics.sh"]
    assert "Invoke-DockerComposeDiagnostics" in by_path["scripts/diagnostics.ps1"]
    assert "Convert-ComposePsJson" not in by_path["scripts/diagnostics.ps1"]


def test_docker_compose_install_loads_image_archives_when_exported() -> None:
    manifest = {**_manifest(), "imageMode": "image-archive"}
    files = render_deployment_files(manifest)
    by_path = {item.path.as_posix(): item.content for item in files}

    assert '"${PACKAGE_ROOT}/scripts/load-images.sh"' in by_path["docker-compose/install.sh"]


def test_docker_compose_install_skips_image_load_for_manifest_only_package() -> None:
    files = render_deployment_files(_manifest())
    by_path = {item.path.as_posix(): item.content for item in files}

    assert '"${PACKAGE_ROOT}/scripts/load-images.sh"' not in by_path["docker-compose/install.sh"]


def test_docker_compose_does_not_inject_runtime_env_file_into_middleware() -> None:
    files = render_deployment_files(_manifest())
    compose = {item.path.as_posix(): item.content for item in files}["docker-compose/docker-compose.yml"]

    assert "env_file:" not in _service_block(compose, "postgres")
    assert "env_file:" not in _service_block(compose, "redis")
    assert "env_file:" not in _service_block(compose, "minio")
    assert "env_file:" not in _service_block(compose, "qdrant")
    app_block = _service_block(compose, "local-ai-eam-service")
    assert "env_file:" in app_block
    assert "DATABASE_URL: postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@postgres:5432/${DATABASE_NAME}" in app_block
    assert "REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0" in app_block
    assert "MINIO_ENDPOINT: minio:9000" in app_block
    assert "MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}" in app_block
    assert "QDRANT_URL: http://qdrant:6333" in app_block


def test_compose_frontend_gateway_is_generated_from_service_specs() -> None:
    manifest = _manifest()
    manifest["businessServices"] = ["mes"]
    manifest["images"]["business"] = ["mes-api-service:prod", "sub-app-mes:prod", "sub-app-quality:prod"]
    manifest["imageEntries"] = [item for item in manifest["imageEntries"] if item["group"] != "business"]
    manifest["imageEntries"].extend(
        [
            {
                "group": "business",
                "sourceRef": "mes-api-service:prod",
                "targetRef": "harbor.example.com/prod/mes-api-service:prod",
                "archiveFile": "mes-api-service_prod.tar",
            },
            {
                "group": "business",
                "sourceRef": "sub-app-mes:prod",
                "targetRef": "harbor.example.com/prod/sub-app-mes:prod",
                "archiveFile": "sub-app-mes_prod.tar",
            },
            {
                "group": "business",
                "sourceRef": "sub-app-quality:prod",
                "targetRef": "harbor.example.com/prod/sub-app-quality:prod",
                "archiveFile": "sub-app-quality_prod.tar",
            },
        ]
    )

    files = render_deployment_files(manifest)
    by_path = {item.path.as_posix(): item.content for item in files}
    compose = by_path["docker-compose/docker-compose.yml"]
    nginx = by_path["docker-compose/frontend-nginx.conf"]

    assert "  local-ai-frontend-shell:" in compose
    assert "      - ./frontend-nginx.conf:/etc/nginx/conf.d/default.conf:ro" in _service_block(compose, "local-ai-frontend-shell")
    assert "location ^~ /sub-app-mes/" in nginx
    assert "location ^~ /sub-app-quality/" in nginx
    assert "rewrite ^/sub\\-app\\-mes/(.*)$ /$1 break;" in nginx
    assert "proxy_pass $sub_app_mes_upstream;" in nginx
    assert "proxy_pass $mes_api_service_upstream$request_uri;" in nginx
    assert "location ^~ /api/mes/" in nginx


def test_camunda_compose_waits_for_elasticsearch_dependency() -> None:
    manifest = _manifest()
    manifest["middleware"] = ["postgres", "camunda", "camunda-elasticsearch"]
    manifest["middlewareConfig"]["camunda"] = {
        "image": "192.168.10.210/local-ai/camunda/camunda:8.8.20",
        "port": 8080,
        "dataPath": "/camunda",
        "dependsOn": ["camunda-elasticsearch"],
        "envTemplate": {
            "CAMUNDA_ADMIN_USER": "demo",
            "CAMUNDA_ADMIN_PASSWORD": "__REPLACE_WITH_CAMUNDA_ADMIN_PASSWORD__",
        },
        "composeEnvironment": {
            "CAMUNDA_ADMIN_USER": "${CAMUNDA_ADMIN_USER}",
            "CAMUNDA_ADMIN_PASSWORD": "${CAMUNDA_ADMIN_PASSWORD}",
            "CAMUNDA_DATA_SECONDARY_STORAGE_ELASTICSEARCH_URL": "http://camunda-elasticsearch:9200",
            "CAMUNDA_DATA_SECONDARY_STORAGE_TYPE": "elasticsearch",
        },
    }
    manifest["middlewareConfig"]["camunda-elasticsearch"] = {
        "image": "192.168.10.210/k8s-platform/docker.elastic.co/elasticsearch/elasticsearch:8.17.4",
        "port": 9200,
        "dataPath": "/usr/share/elasticsearch/data",
        "composeEnvironment": {
            "discovery.type": "single-node",
            "xpack.security.enabled": "false",
        },
        "composeHealthcheck": {
            "test": ["CMD-SHELL", "bash -lc '</dev/tcp/127.0.0.1/9200'"],
            "interval": "20s",
            "timeout": "5s",
            "retries": 30,
            "startPeriod": "60s",
        },
    }
    manifest["imageEntries"].extend(
        [
            {
                "group": "middleware",
                "sourceRef": "192.168.10.210/local-ai/camunda/camunda:8.8.20",
                "targetRef": "harbor.example.com/prod/camunda/camunda:8.8.20",
                "archiveFile": "camunda.tar",
            },
            {
                "group": "middleware",
                "sourceRef": "192.168.10.210/k8s-platform/docker.elastic.co/elasticsearch/elasticsearch:8.17.4",
                "targetRef": "harbor.example.com/prod/docker.elastic.co/elasticsearch/elasticsearch:8.17.4",
                "archiveFile": "camunda-elasticsearch.tar",
            },
        ]
    )

    files = render_deployment_files(manifest)
    by_path = {item.path.as_posix(): item.content for item in files}
    compose = by_path["docker-compose/docker-compose.yml"]

    assert "  camunda-elasticsearch:" in compose
    assert "CAMUNDA_DATA_SECONDARY_STORAGE_ELASTICSEARCH_URL: http://camunda-elasticsearch:9200" in compose
    assert "xpack.security.enabled: \"false\"" in compose
    assert "  camunda:\n" in compose
    assert "      camunda-elasticsearch:\n        condition: service_healthy" in compose
    workflow_deployments = by_path["k8s/layers/40-workflow-webui/deployments.yaml"]
    assert "name: camunda-elasticsearch" in workflow_deployments
    assert "name: CAMUNDA_DATA_SECONDARY_STORAGE_ELASTICSEARCH_URL" in workflow_deployments
    assert 'value: "http://camunda-elasticsearch:9200"' in workflow_deployments
    assert "name: CAMUNDA_ADMIN_PASSWORD" in workflow_deployments
    assert "secretKeyRef:" in workflow_deployments
    assert "key: CAMUNDA_ADMIN_PASSWORD" in workflow_deployments


def _service_block(compose: str, service_name: str) -> str:
    lines = compose.splitlines()
    start = next(index for index, line in enumerate(lines) if line == f"  {service_name}:")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            end = index
            break
    return "\n".join(lines[start:end])


def _manifest() -> dict:
    return {
        "packageId": "pkg-test",
        "createdAt": "2026-06-27T00:00:00+00:00",
        "projectKey": None,
        "productVersion": "2026.06",
        "sourceEnv": "test",
        "targetEnv": "prod",
        "deployModes": ["k8s", "docker-compose"],
        "database": "postgres",
        "databaseImage": "postgres:16",
        "imageMode": "image-manifest",
        "platformServices": ["iam", "gateway"],
        "businessServices": ["eam"],
        "middleware": ["postgres", "redis", "minio", "qdrant"],
        "middlewareConfig": {
            "postgres": {
                "port": 5432,
                "dataPath": "/var/lib/postgresql/data",
                "envTemplate": {
                    "DATABASE_USER": "local_ai",
                    "DATABASE_NAME": "local_ai",
                    "DATABASE_PASSWORD": "__REPLACE_WITH_DATABASE_PASSWORD__",
                },
                "composeEnvironment": {
                    "POSTGRES_USER": "${DATABASE_USER}",
                    "POSTGRES_PASSWORD": "${DATABASE_PASSWORD}",
                    "POSTGRES_DB": "${DATABASE_NAME}",
                },
                "composeHealthcheck": {
                    "test": ["CMD-SHELL", 'pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'],
                    "interval": "20s",
                    "timeout": "5s",
                    "retries": 10,
                    "startPeriod": "20s",
                },
            },
            "redis": {
                "port": 6379,
                "dataPath": "/data",
                "envTemplate": {"REDIS_PASSWORD": "__REPLACE_WITH_REDIS_PASSWORD__"},
                "composeEnvironment": {"REDIS_PASSWORD": "${REDIS_PASSWORD}"},
                "composeCommand": ["redis-server", "--requirepass", "${REDIS_PASSWORD}"],
                "composeHealthcheck": {
                    "test": ["CMD-SHELL", 'redis-cli -a "$$REDIS_PASSWORD" ping'],
                    "interval": "20s",
                    "timeout": "5s",
                    "retries": 10,
                    "startPeriod": "10s",
                },
            },
            "minio": {
                "port": 9000,
                "dataPath": "/data",
                "envTemplate": {
                    "MINIO_ROOT_USER": "local-ai",
                    "MINIO_ROOT_PASSWORD": "__REPLACE_WITH_MINIO_ROOT_PASSWORD__",
                },
                "composeEnvironment": {
                    "MINIO_ROOT_USER": "${MINIO_ROOT_USER}",
                    "MINIO_ROOT_PASSWORD": "${MINIO_ROOT_PASSWORD}",
                },
                "composeCommand": ["server", "/data", "--console-address", ":9001"],
            },
            "qdrant": {
                "port": 6333,
                "dataPath": "/qdrant/storage",
                "envTemplate": {"QDRANT_API_KEY": "__REPLACE_WITH_QDRANT_API_KEY__"},
                "composeEnvironment": {"QDRANT__SERVICE__API_KEY": "${QDRANT_API_KEY}"},
            },
        },
        "_runtimeEnv": {
            "DATABASE_USER": "local_ai",
            "DATABASE_NAME": "local_ai",
            "DATABASE_PASSWORD": "source-db-password",
            "REDIS_PASSWORD": "source-redis-password",
            "MINIO_ROOT_USER": "local-ai",
            "MINIO_ROOT_PASSWORD": "source-minio-password",
            "QDRANT_API_KEY": "source-qdrant-key",
        },
        "targetProfile": {
            "env": "prod",
            "registry": "harbor.example.com/prod",
            "namespacePrefix": "prod",
            "domain": "eam.example.com",
            "storageClass": "fast-ssd",
            "exportImages": False,
        },
        "images": {
            "platform": ["local-ai-iam-service:prod", "local-ai-frontend-shell:prod"],
            "business": ["local-ai-eam-service:prod"],
            "middleware": ["postgres:16", "redis:7", "minio/minio:latest", "qdrant/qdrant:latest"],
        },
        "imageEntries": [
            {
                "group": "business",
                "sourceRef": "local-ai-eam-service:prod",
                "targetRef": "harbor.example.com/prod/local-ai-eam-service:prod",
                "archiveFile": "local-ai-eam-service_prod.tar",
            },
            {
                "group": "middleware",
                "sourceRef": "postgres:16",
                "targetRef": "harbor.example.com/prod/postgres:16",
                "archiveFile": "postgres_16.tar",
            },
            {
                "group": "middleware",
                "sourceRef": "redis:7",
                "targetRef": "harbor.example.com/prod/redis:7",
                "archiveFile": "redis_7.tar",
            },
            {
                "group": "middleware",
                "sourceRef": "minio/minio:latest",
                "targetRef": "harbor.example.com/prod/minio/minio:latest",
                "archiveFile": "minio_minio_latest.tar",
            },
            {
                "group": "middleware",
                "sourceRef": "qdrant/qdrant:latest",
                "targetRef": "harbor.example.com/prod/qdrant/qdrant:latest",
                "archiveFile": "qdrant_qdrant_latest.tar",
            },
            {
                "group": "platform",
                "sourceRef": "local-ai-frontend-shell:prod",
                "targetRef": "harbor.example.com/prod/local-ai-frontend-shell:prod",
                "archiveFile": "local-ai-frontend-shell_prod.tar",
            },
            {
                "group": "platform",
                "sourceRef": "local-ai-iam-service:prod",
                "targetRef": "harbor.example.com/prod/local-ai-iam-service:prod",
                "archiveFile": "local-ai-iam-service_prod.tar",
            },
        ],
    }
