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
    assert {"postgres", "redis", "minio", "camunda", "iotdb"}.issubset(middleware_keys)
    assert "local-ai-eam-service" in preview.images["business"]

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


def test_unknown_database_is_rejected() -> None:
    catalog = load_catalog()
    with pytest.raises(CatalogError):
        resolve_package_preview(PackagePreviewRequest(database="mysql"), catalog)
