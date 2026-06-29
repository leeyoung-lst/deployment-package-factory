from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from deployment_package_factory.settings import DeploymentPackageSettings
from deployment_package_factory.services.deployment_packages.models import ImageExportEnvironmentCheck


CheckStatus = str


def build_readiness_report(
    *,
    settings: DeploymentPackageSettings,
    task_repository: Callable[[], object],
    audit_repository: Callable[[], object],
    business_platform_repository: Callable[[], object],
    microservice_repository: Callable[[], object],
    image_export_environment: Callable[[], ImageExportEnvironmentCheck],
) -> dict:
    checks = [
        _run_check("database_url", True, lambda: _check_database_url(settings.database_url)),
        _run_check("metadata_store", True, lambda: _check_metadata_store(
            task_repository,
            audit_repository,
            business_platform_repository,
            microservice_repository,
        )),
        _run_check("output_dir", True, lambda: _check_writable_directory(settings.output_dir)),
        _run_check("image_export", False, lambda: _check_image_export(image_export_environment())),
    ]
    required_failed = any(item["required"] and item["status"] != "ok" for item in checks)
    warnings = any(item["status"] == "warning" for item in checks)
    status = "not_ready" if required_failed else "degraded" if warnings else "ready"
    return {"status": status, "checks": checks}


def _run_check(name: str, required: bool, check: Callable[[], tuple[CheckStatus, str, dict | None]]) -> dict:
    try:
        status, message, details = check()
    except Exception as exc:
        status = "failed" if required else "warning"
        message = str(exc)
        details = {"exception": exc.__class__.__name__}
    payload = {
        "name": name,
        "required": required,
        "status": status,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def _check_database_url(database_url: str) -> tuple[CheckStatus, str, dict | None]:
    if not database_url.strip():
        return "failed", "DEPLOYMENT_PACKAGE_DATABASE_URL is not configured.", None
    return "ok", "DEPLOYMENT_PACKAGE_DATABASE_URL is configured.", None


def _check_metadata_store(
    task_repository: Callable[[], object],
    audit_repository: Callable[[], object],
    business_platform_repository: Callable[[], object],
    microservice_repository: Callable[[], object],
) -> tuple[CheckStatus, str, dict | None]:
    task_summary = task_repository().metrics_summary()
    audit_summary = audit_repository().metrics_summary()
    business_count = len(business_platform_repository().list(include_disabled=True))
    microservice_count = len(microservice_repository().list())
    return (
        "ok",
        "PostgreSQL metadata store is reachable and schema checks passed.",
        {
            "tasks": int(task_summary.get("total", 0)),
            "auditEvents": int(audit_summary.get("total", 0)),
            "businessPlatforms": business_count,
            "microservices": microservice_count,
        },
    )


def _check_writable_directory(path: Path) -> tuple[CheckStatus, str, dict | None]:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / f".readiness-{uuid4().hex}.tmp"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)
    return "ok", f"{path} is writable.", {"path": str(path)}


def _check_image_export(result: ImageExportEnvironmentCheck) -> tuple[CheckStatus, str, dict | None]:
    status = "ok" if result.available else "warning"
    details = {
        "exportTool": result.export_tool,
        "toolVersion": result.tool_version,
        "dockerVersion": result.docker_version,
    }
    return status, result.message, details
