from __future__ import annotations

import pytest

from deployment_package_factory.services.deployment_packages import repositories
from deployment_package_factory.services.deployment_packages.postgres_repositories import PostgresAuditEventRepository
from deployment_package_factory.services.deployment_packages.repositories import (
    create_audit_repository,
    create_business_platform_repository,
    create_task_repository,
)
from deployment_package_factory.services.microservices import repository as microservice_repositories
from deployment_package_factory.services.microservices.repository import create_microservice_repository
import psycopg


def test_repository_factory_requires_database_url_when_missing() -> None:
    for factory in [
        create_task_repository,
        create_audit_repository,
        create_business_platform_repository,
        create_microservice_repository,
    ]:
        with pytest.raises(RuntimeError, match="DEPLOYMENT_PACKAGE_DATABASE_URL is required"):
            factory(database_url="")


def test_repository_factory_uses_postgres_when_database_url_is_configured(monkeypatch) -> None:
    database_url = "postgresql://factory:secret@postgres:5432/factory"
    task_marker = object()
    audit_marker = object()
    business_marker = object()
    microservice_marker = object()

    monkeypatch.setattr(repositories, "PostgresPackageTaskRepository", lambda value: task_marker)
    monkeypatch.setattr(repositories, "PostgresAuditEventRepository", lambda value: audit_marker)
    monkeypatch.setattr(repositories, "PostgresBusinessPlatformRepository", lambda value: business_marker)
    monkeypatch.setattr(microservice_repositories, "MicroserviceRepository", lambda value: microservice_marker)

    assert create_task_repository(database_url=database_url) is task_marker
    assert create_audit_repository(database_url=database_url) is audit_marker
    assert create_business_platform_repository(database_url=database_url) is business_marker
    assert create_microservice_repository(database_url=database_url) is microservice_marker

def test_postgres_audit_repository_retries_after_missing_schema(monkeypatch) -> None:
    repo = object.__new__(PostgresAuditEventRepository)
    repo.database_url = "postgresql://factory:secret@postgres:5432/factory"
    calls = {"operation": 0, "ensure_schema": 0}

    def operation() -> str:
        calls["operation"] += 1
        if calls["operation"] == 1:
            raise psycopg.errors.UndefinedTable("relation audit_events does not exist")
        return "ok"

    def ensure_schema() -> None:
        calls["ensure_schema"] += 1

    monkeypatch.setattr(repo, "_ensure_schema", ensure_schema)

    assert repo._with_schema_retry(operation) == "ok"
    assert calls == {"operation": 2, "ensure_schema": 1}
