from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from deployment_package_factory.auth import require_api_token
from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.settings import (
    SystemSettings,
    create_system_settings_repository,
)
from deployment_package_factory.services.settings_importer import import_environment_settings_from_xlsx

MAX_XLSX_IMPORT_BYTES = 50 * 1024 * 1024  # 50 MB

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_api_token)],
)

_SETTINGS = load_settings()
_SETTINGS_REPO = None
_SETTINGS_REPO_LOCK = threading.Lock()


class EnvironmentSettingsImportResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    settings: SystemSettings
    imported_fields: list[str] = Field(alias="importedFields")
    warnings: list[str] = Field(default_factory=list)


def get_system_settings_repository():
    global _SETTINGS_REPO
    with _SETTINGS_REPO_LOCK:
        if _SETTINGS_REPO is None:
            _SETTINGS_REPO = create_system_settings_repository(database_url=_SETTINGS.database_url)
        return _SETTINGS_REPO


@router.get("", response_model=SystemSettings)
async def get_system_settings() -> SystemSettings:
    return get_system_settings_repository().get()


@router.put("", response_model=SystemSettings)
async def update_system_settings(payload: SystemSettings) -> SystemSettings:
    return get_system_settings_repository().update(payload)


@router.post("/import-environment", response_model=EnvironmentSettingsImportResult)
async def import_environment_settings(payload: bytes = Body(...)) -> EnvironmentSettingsImportResult:
    if len(payload) > MAX_XLSX_IMPORT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"XLSX file exceeds maximum allowed size of {MAX_XLSX_IMPORT_BYTES // (1024 * 1024)} MB.",
        )
    repository = get_system_settings_repository()
    current = repository.get()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    try:
        result = import_environment_settings_from_xlsx(temp_path, current)
    finally:
        temp_path.unlink(missing_ok=True)
    saved = repository.update(result.settings)
    return EnvironmentSettingsImportResult(
        settings=saved,
        importedFields=result.imported_fields,
        warnings=result.warnings,
    )
