from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from deployment_package_factory.services.deployment_packages.models import (
    Capability,
    DatabaseOption,
    DeploymentCatalog,
    MiddlewareOption,
    ProjectProfile,
)
from deployment_package_factory.services.deployment_packages.template_paths import default_catalog_dir


class CatalogError(ValueError):
    pass


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise CatalogError(f"Catalog file {path} must contain a YAML mapping.")
    return data


def _capabilities(raw: dict[str, Any], section: str) -> dict[str, Capability]:
    values = raw.get(section) or {}
    if not isinstance(values, dict):
        raise CatalogError(f"Catalog section {section!r} must be a mapping.")
    result: dict[str, Capability] = {}
    for key, payload in values.items():
        if not isinstance(payload, dict):
            raise CatalogError(f"Capability {key!r} must be a mapping.")
        if key in result:
            raise CatalogError(f"Duplicate capability key {key!r}.")
        result[key] = Capability.model_validate({"key": key, **payload})
    return result


def load_catalog(catalog_dir: Path | None = None) -> DeploymentCatalog:
    base = catalog_dir or default_catalog_dir()
    platform_raw = _read_yaml(base / "platform.yaml")
    business_raw = _read_yaml(base / "business.yaml")
    middleware_raw = _read_yaml(base / "middleware.yaml")
    rules_raw = _read_yaml(base / "dependency-rules.yaml")
    projects_raw = _read_yaml(base / "projects.yaml")

    platform = _capabilities(platform_raw, "platform")
    business = _capabilities(business_raw, "business")
    database_options = {
        key: DatabaseOption.model_validate({"key": key, **value})
        for key, value in (middleware_raw.get("databaseOptions") or {}).items()
    }
    middleware = {
        key: MiddlewareOption.model_validate({"key": key, **value})
        for key, value in (middleware_raw.get("middleware") or {}).items()
    }
    projects = {
        key: ProjectProfile.model_validate({"key": key, **value})
        for key, value in (projects_raw.get("projects") or {}).items()
    }

    _validate_catalog(platform, business, database_options, middleware, projects)

    defaults = (rules_raw.get("defaults") or {}).get("platform") or []
    allowed = (rules_raw.get("database") or {}).get("allowed") or list(database_options)
    return DeploymentCatalog(
        platform=platform,
        business=business,
        database_options=database_options,
        middleware=middleware,
        projects=projects,
        default_platform=list(defaults),
        allowed_databases=list(allowed),
    )


def _validate_catalog(
    platform: dict[str, Capability],
    business: dict[str, Capability],
    database_options: dict[str, DatabaseOption],
    middleware: dict[str, MiddlewareOption],
    projects: dict[str, ProjectProfile],
) -> None:
    overlap = set(platform) & set(business)
    if overlap:
        raise CatalogError(f"Capability keys cannot appear in both platform and business sections: {sorted(overlap)}")
    if not database_options:
        raise CatalogError("At least one database option is required.")

    platform_keys = set(platform)
    middleware_keys = set(middleware) | {"database"} | set(database_options)
    for capability in [*platform.values(), *business.values()]:
        if not capability.namespace_group:
            raise CatalogError(f"Capability {capability.key!r} must declare namespaceGroup.")
        missing_platform = set(capability.depends_on) - platform_keys
        if missing_platform:
            raise CatalogError(f"Capability {capability.key!r} depends on unknown platform services: {sorted(missing_platform)}")
        missing_middleware = set(capability.middleware) - middleware_keys
        if missing_middleware:
            raise CatalogError(f"Capability {capability.key!r} depends on unknown middleware: {sorted(missing_middleware)}")

    for project in projects.values():
        missing_platform = set(project.default_platform_services) - set(platform)
        if missing_platform:
            raise CatalogError(f"Project {project.key!r} references unknown platform services: {sorted(missing_platform)}")
        missing_business = {item.name for item in project.default_business_services} - set(business)
        if missing_business:
            raise CatalogError(f"Project {project.key!r} references unknown business services: {sorted(missing_business)}")
        if project.default_database not in database_options:
            raise CatalogError(f"Project {project.key!r} references unknown database {project.default_database!r}.")
