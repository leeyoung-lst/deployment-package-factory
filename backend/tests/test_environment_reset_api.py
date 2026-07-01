from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from deployment_package_factory.api import _common, environment_reset
from deployment_package_factory.services.environment_reset import (
    EnvironmentResetOptions,
    EnvironmentResetPreview,
    EnvironmentResetRequest,
    ResetPathSummary,
    ResetTableSummary,
)
from fakes import InMemoryAuditEventRepository, InMemoryTaskRepository


@pytest.fixture(autouse=True)
def _isolate_repositories(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_common, "_TASK_REPO", InMemoryTaskRepository())
    monkeypatch.setattr(_common, "_AUDIT_REPO", InMemoryAuditEventRepository())


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(environment_reset.router)
    return TestClient(app)


def test_preview_environment_reset_returns_selected_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_preview(database_url, output_dir, options: EnvironmentResetOptions) -> EnvironmentResetPreview:
        return EnvironmentResetPreview(
            tables=[
                ResetTableSummary(name="packageTasks", selected=options.package_tasks, existingRows=2),
                ResetTableSummary(name="auditEvents", selected=options.audit_events, existingRows=3),
            ],
            paths=[
                ResetPathSummary(name="packageArtifacts", path="/data/artifacts", selected=options.package_artifacts, exists=True, files=4, bytes=128),
            ],
            totalRows=5,
            selectedRows=2,
            totalFiles=4,
            selectedFiles=4,
            totalBytes=128,
            selectedBytes=128,
        )

    monkeypatch.setattr(environment_reset, "preview_environment_reset", fake_preview)

    response = _client().post("/api/environment-reset/preview", json={"auditEvents": False})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["dryRun"] is True
    assert payload["confirmationPhrase"] == "RESET deployment-package-factory"
    assert payload["selectedRows"] == 2
    assert payload["selectedBytes"] == 128


def test_execute_environment_reset_requires_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_execute(database_url, output_dir, request: EnvironmentResetRequest) -> EnvironmentResetPreview:
        raise ValueError("Confirmation must be exactly: RESET deployment-package-factory")

    monkeypatch.setattr(environment_reset, "execute_environment_reset", fake_execute)

    response = _client().post("/api/environment-reset/execute", json={"confirmation": "wrong"})

    assert response.status_code == 400
    assert "RESET deployment-package-factory" in response.text


def test_execute_environment_reset_records_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    audit_repo = InMemoryAuditEventRepository()
    monkeypatch.setattr(_common, "_AUDIT_REPO", audit_repo)

    def fake_execute(database_url, output_dir, request: EnvironmentResetRequest) -> EnvironmentResetPreview:
        return EnvironmentResetPreview(
            dryRun=False,
            tables=[ResetTableSummary(name="packageTasks", selected=True, existingRows=2, deletedRows=2)],
            deletedRows=2,
        )

    monkeypatch.setattr(environment_reset, "execute_environment_reset", fake_execute)

    response = _client().post(
        "/api/environment-reset/execute",
        headers={"X-Deployment-Package-Operator": "ops"},
        json={"confirmation": "RESET deployment-package-factory"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["deletedRows"] == 2
    events = audit_repo.list(limit=10)
    assert events[0].action == "environment.reset"
    assert events[0].operator == "ops"
    assert events[0].metadata["deletedRows"] == 2
