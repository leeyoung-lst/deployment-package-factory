from __future__ import annotations

from deployment_package_factory.services.deployment_packages.audit_repository import AuditEventRepository


def test_audit_repository_records_and_lists_events(tmp_path) -> None:
    repo = AuditEventRepository(tmp_path / "audit.sqlite3")

    created = repo.record(
        action="package.create",
        status="accepted",
        target_id="task-1",
        operator="alice",
        client_ip="127.0.0.1",
        message="created",
        metadata={"database": "postgres"},
    )
    repo.record(action="package.cleanup", status="dry-run")

    events = repo.list(limit=10)

    assert len(events) == 2
    assert events[1].event_id == created.event_id
    assert events[1].operator == "alice"
    assert events[1].metadata == {"database": "postgres"}


def test_audit_repository_limits_events(tmp_path) -> None:
    repo = AuditEventRepository(tmp_path / "audit.sqlite3")
    repo.record(action="a", status="completed")
    repo.record(action="b", status="completed")

    events = repo.list(limit=1)

    assert len(events) == 1
