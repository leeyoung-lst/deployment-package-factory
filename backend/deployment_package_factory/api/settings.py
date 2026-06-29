from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, ConfigDict, Field

from deployment_package_factory.auth import require_api_token
from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.settings import (
    SystemSettings,
    create_system_settings_repository,
)
from deployment_package_factory.services.settings_importer import import_environment_settings_from_xlsx

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_api_token)],
)

_SETTINGS = load_settings()
_SETTINGS_REPO = None


class EnvironmentSettingsImportResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    settings: SystemSettings
    imported_fields: list[str] = Field(alias="importedFields")
    warnings: list[str] = Field(default_factory=list)


def get_system_settings_repository():
    global _SETTINGS_REPO
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
