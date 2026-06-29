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
    assert not by_path["k8s/namespaces.yaml"].executable
    assert not by_path["docker-compose/docker-compose.yml"].executable
    assert by_path["k8s/install.sh"].executable
    assert by_path["docker-compose/dry-run.sh"].executable
    assert by_path["scripts/secret-check.sh"].executable


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
    assert "name: init-scripts" in by_path["k8s/jobs/init-db.yaml"]
    assert "command: [\"/bin/sh\", \"/init/run-init.sh\"]" in by_path["k8s/jobs/init-db.yaml"]
    assert '"${PACKAGE_ROOT}/scripts/secret-check.sh" k8s' in by_path["k8s/install.sh"]
    assert '"${PACKAGE_ROOT}/scripts/secret-check.sh" docker-compose' in by_path["docker-compose/install.sh"]
    assert '"${PACKAGE_ROOT}/init/run-init.sh" all' in by_path["docker-compose/install.sh"]
    assert "check_disk_space" in by_path["scripts/check-prerequisites.sh"]
    assert "check_image_archives" in by_path["scripts/check-prerequisites.sh"]
    assert "Missing image archives" in by_path["scripts/check-prerequisites.sh"]


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
            },
            "redis": {
                "port": 6379,
                "dataPath": "/data",
                "envTemplate": {"REDIS_PASSWORD": "__REPLACE_WITH_REDIS_PASSWORD__"},
                "composeEnvironment": {"REDIS_PASSWORD": "${REDIS_PASSWORD}"},
                "composeCommand": ["redis-server", "--requirepass", "${REDIS_PASSWORD}"],
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
