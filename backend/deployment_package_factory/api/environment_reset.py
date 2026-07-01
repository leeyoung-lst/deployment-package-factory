from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from deployment_package_factory.auth import require_api_token
from deployment_package_factory.settings import load_settings
from deployment_package_factory.api._common import get_audit_repository
from deployment_package_factory.services.environment_reset import (
    EnvironmentResetOptions,
    EnvironmentResetPreview,
    EnvironmentResetRequest,
    execute_environment_reset,
    preview_environment_reset,
)

router = APIRouter(
    prefix="/api/environment-reset",
    tags=["environment-reset"],
    dependencies=[Depends(require_api_token)],
)
_SETTINGS = load_settings()


@router.post("/preview", response_model=EnvironmentResetPreview)
async def preview_reset(payload: EnvironmentResetOptions | None = None) -> EnvironmentResetPreview:
    try:
        return preview_environment_reset(_SETTINGS.database_url, _SETTINGS.output_dir, payload or EnvironmentResetOptions())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/execute", response_model=EnvironmentResetPreview)
async def execute_reset(
    payload: EnvironmentResetRequest,
    request: Request,
    x_deployment_package_operator: str | None = Header(default=None),
) -> EnvironmentResetPreview:
    try:
        result = execute_environment_reset(_SETTINGS.database_url, _SETTINGS.output_dir, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_reset(request, result, x_deployment_package_operator)
    return result


def _audit_reset(request: Request, result: EnvironmentResetPreview, operator: str | None) -> None:
    try:
        get_audit_repository().record(
            action="environment.reset",
            status="completed",
            target_id=result.namespace,
            operator=_operator(request, operator),
            client_ip=_client_ip(request),
            message="Deployment package factory environment reset completed.",
            metadata=result.model_dump(by_alias=True),
        )
    except Exception:
        return


def _operator(request: Request, explicit_operator: str | None) -> str:
    if explicit_operator and explicit_operator.strip():
        return explicit_operator.strip()
    if getattr(request.state, "deployment_package_authenticated", False):
        return "api-token"
    return "anonymous"


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else ""
