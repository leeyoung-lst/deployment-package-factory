from __future__ import annotations

from pathlib import Path

from deployment_package_factory.services.deployment_packages.audit_repository import AuditEventRepository
from deployment_package_factory.services.deployment_packages.business_platform_repository import BusinessPlatformRepository
from deployment_package_factory.services.deployment_packages.postgres_repositories import (
    PostgresAuditEventRepository,
    PostgresBusinessPlatformRepository,
    PostgresPackageTaskRepository,
)
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository


def create_task_repository(*, database_url: str = "", sqlite_path: Path | None = None):
    if database_url:
        return PostgresPackageTaskRepository(database_url)
    return PackageTaskRepository(sqlite_path)


def create_audit_repository(*, database_url: str = "", sqlite_path: Path | None = None):
    if database_url:
        return PostgresAuditEventRepository(database_url)
    return AuditEventRepository(sqlite_path)


def create_business_platform_repository(*, database_url: str = "", sqlite_path: Path | None = None):
    if database_url:
        return PostgresBusinessPlatformRepository(database_url)
    return BusinessPlatformRepository(sqlite_path)
