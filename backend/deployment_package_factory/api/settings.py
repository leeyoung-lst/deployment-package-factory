from __future__ import annotations

from fastapi import APIRouter, Depends

from deployment_package_factory.auth import require_api_token
from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.settings import (
    SystemSettings,
    create_system_settings_repository,
)

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_api_token)],
)

_SETTINGS = load_settings()
_SETTINGS_REPO = None


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
