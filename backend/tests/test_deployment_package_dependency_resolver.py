from __future__ import annotations

import pytest

from deployment_package_factory.services.deployment_packages.catalog import CatalogError, load_catalog
from deployment_package_factory.services.deployment_packages.dependency_resolver import resolve_package_preview
from deployment_package_factory.services.deployment_packages.models import BusinessSelection, PackagePreviewRequest


def test_catalog_loads_default_capabilities() -> None:
    catalog = load_catalog()

    assert "iam" in catalog.platform
    assert "eam" in catalog.business
    assert "postgres" in catalog.database_options
    assert "dm" in catalog.database_options
    assert "standard-eam" in catalog.projects
    assert catalog.projects["mes-lite"].default_database == "dm"
    assert catalog.middleware["redis"].port == 6379
    assert catalog.middleware["redis"].compose_command == ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]
    assert catalog.middleware["redis"].compose_healthcheck["test"] == ["CMD-SHELL", 'redis-cli -a "$$REDIS_PASSWORD" ping']
    assert catalog.middleware["redis"].env_template["REDIS_PASSWORD"] == "__REPLACE_WITH_REDIS_PASSWORD__"
    assert catalog.middleware["redis"].env_sources["REDIS_PASSWORD"]["secretKeys"] == ["REDIS_PASSWORD"]
    assert catalog.middleware["camunda"].depends_on == ["camunda-elasticsearch"]
    assert catalog.database_options["postgres"].compose_environment["POSTGRES_PASSWORD"] == "${DATABASE_PASSWORD}"
    assert catalog.database_options["postgres"].env_sources["DATABASE_PASSWORD"]["secretKeys"] == ["DATABASE_PASSWORD", "POSTGRES_PASSWORD"]


def test_eam_preview_resolves_platform_and_middleware_dependencies() -> None:
    catalog = load_catalog()
    preview = resolve_package_preview(
        PackagePreviewRequest(
            sourceEnv="test",
            deployModes=["k8s", "docker-compose"],
            platformServices=[],
            businessServices=[BusinessSelection(name="eam", profile="4x60")],
            database="postgres",
        ),
        catalog,
    )

    platform_keys = {item.key for item in preview.platform_services}
    middleware_keys = {item.key for item in preview.middleware}

    assert {"iam", "gateway-frontend", "file-documents", "workflow-camunda", "audit"}.issubset(platform_keys)
    assert {"postgres", "redis", "minio", "camunda", "camunda-elasticsearch", "iotdb"}.issubset(middleware_keys)
    assert "local-ai-eam-service" in preview.images["business"]
    assert "192.168.10.210/k8s-platform/docker.elastic.co/elasticsearch/elasticsearch:8.17.4" in preview.images["middleware"]
    assert "192.168.10.210/local-ai/nginx:1.27-alpine" in preview.images["support"]

    redis = next(item for item in preview.middleware if item.key == "redis")
    assert redis.locked is True
    assert "eam" in redis.required_by


def test_ai_agent_preview_resolves_qdrant_and_audit() -> None:
    catalog = load_catalog()
    preview = resolve_package_preview(
        PackagePreviewRequest(platformServices=["ai-agent"], businessServices=[], database="postgres"),
        catalog,
    )

    platform_keys = {item.key for item in preview.platform_services}
    middleware_keys = {item.key for item in preview.middleware}

    assert "audit" in platform_keys
    assert "qdrant" in middleware_keys
    assert "redis" in middleware_keys


def test_project_defaults_drive_preview_selection() -> None:
    catalog = load_catalog()
    preview = resolve_package_preview(PackagePreviewRequest(projectKey="mes-lite"), catalog)

    assert [item.key for item in preview.business_services] == ["mes"]
    assert preview.database.key == "dm"
    assert "dm" in {item.key for item in preview.middleware}
    assert any("国产化数据库" in warning for warning in preview.warnings)


def test_unknown_database_is_rejected() -> None:
    catalog = load_catalog()
    with pytest.raises(CatalogError):
        resolve_package_preview(PackagePreviewRequest(database="mysql"), catalog)


def test_database_disallowed_by_rules_is_rejected() -> None:
    catalog = load_catalog().model_copy(update={"allowed_databases": ["postgres"]})
    with pytest.raises(CatalogError, match="not allowed"):
        resolve_package_preview(PackagePreviewRequest(database="dm"), catalog)


def test_preview_warns_when_no_business_service_selected() -> None:
    catalog = load_catalog()
    preview = resolve_package_preview(
        PackagePreviewRequest(platformServices=["ai-agent"], businessServices=[], database="postgres"),
        catalog,
    )

    assert any("未选择核心业务服务" in warning for warning in preview.warnings)


def test_unknown_project_is_rejected() -> None:
    catalog = load_catalog()
    with pytest.raises(CatalogError):
        resolve_package_preview(PackagePreviewRequest(projectKey="missing-project"), catalog)
