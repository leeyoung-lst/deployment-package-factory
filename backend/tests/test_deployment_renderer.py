from __future__ import annotations

from deployment_package_factory.services.deployment_packages.deployment_renderer import render_deployment_files


def test_render_deployment_files_declares_expected_paths_and_executable_flags() -> None:
    files = render_deployment_files(_manifest())
    by_path = {item.path.as_posix(): item for item in files}

    assert "k8s/namespaces.yaml" in by_path
    assert "k8s/install.sh" in by_path
    assert "docker-compose/docker-compose.yml" in by_path
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
    assert "harbor.example.com/prod/postgres:16" in by_path["docker-compose/docker-compose.yml"]
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
        "middleware": ["postgres", "redis"],
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
            "middleware": ["postgres:16", "redis:7"],
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
