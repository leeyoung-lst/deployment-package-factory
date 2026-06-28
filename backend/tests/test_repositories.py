from __future__ import annotations

from deployment_package_factory.services.deployment_packages.audit_repository import AuditEventRepository
from deployment_package_factory.services.deployment_packages.business_platform_repository import BusinessPlatformRepository
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import RegisteredBusinessPlatform
from deployment_package_factory.services.deployment_packages import repositories
from deployment_package_factory.services.deployment_packages.postgres_repositories import PostgresAuditEventRepository
from deployment_package_factory.services.deployment_packages.repositories import (
    create_audit_repository,
    create_business_platform_repository,
    create_task_repository,
)
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository
import psycopg


def test_repository_factory_uses_sqlite_when_database_url_is_empty(tmp_path) -> None:
    assert isinstance(create_task_repository(sqlite_path=tmp_path / "tasks.sqlite3"), PackageTaskRepository)
    assert isinstance(create_audit_repository(sqlite_path=tmp_path / "audit.sqlite3"), AuditEventRepository)
    assert isinstance(create_business_platform_repository(sqlite_path=tmp_path / "business.sqlite3"), BusinessPlatformRepository)


def test_repository_factory_uses_postgres_when_database_url_is_configured(monkeypatch) -> None:
    database_url = "postgresql://factory:secret@postgres:5432/factory"
    task_marker = object()
    audit_marker = object()
    business_marker = object()

    monkeypatch.setattr(repositories, "PostgresPackageTaskRepository", lambda value: task_marker)
    monkeypatch.setattr(repositories, "PostgresAuditEventRepository", lambda value: audit_marker)
    monkeypatch.setattr(repositories, "PostgresBusinessPlatformRepository", lambda value: business_marker)

    assert create_task_repository(database_url=database_url) is task_marker
    assert create_audit_repository(database_url=database_url) is audit_marker
    assert create_business_platform_repository(database_url=database_url) is business_marker


def test_business_platform_repository_persists_registered_platform(tmp_path) -> None:
    repo = BusinessPlatformRepository(tmp_path / "business.sqlite3")
    platform = repo.upsert_registered(
        RegisteredBusinessPlatform(
            key="eam",
            name="EAM",
            profile="4x60",
            namespace="test-biz-eam-4x60",
            source_env="test",
        ),
        metadata={"operator": "alice"},
    )

    assert platform.namespace == "test-biz-eam-4x60"
    assert repo.resolve("test", "eam", "4x60").metadata["operator"] == "alice"
    assert [item.key for item in repo.list("test")] == ["eam"]

    disabled = repo.disable("test", "eam", "4x60")

    assert disabled.status == "disabled"
    assert repo.list("test") == []
    assert repo.list("test", include_disabled=True)[0].status == "disabled"


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
