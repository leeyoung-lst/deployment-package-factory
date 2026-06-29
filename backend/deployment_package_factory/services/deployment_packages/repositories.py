from __future__ import annotations

from deployment_package_factory.services.deployment_packages.postgres_repositories import (
    PostgresAuditEventRepository,
    PostgresBusinessPlatformRepository,
    PostgresPackageTaskRepository,
)


def create_task_repository(*, database_url: str = ""):
    return PostgresPackageTaskRepository(_require_database_url(database_url))


def create_audit_repository(*, database_url: str = ""):
    return PostgresAuditEventRepository(_require_database_url(database_url))


def create_business_platform_repository(*, database_url: str = ""):
    return PostgresBusinessPlatformRepository(_require_database_url(database_url))


def _require_database_url(database_url: str) -> str:
    if not database_url.strip():
        raise RuntimeError("DEPLOYMENT_PACKAGE_DATABASE_URL is required for PostgreSQL persistence.")
    return database_url.strip()
