"""Business platform registration and management API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from deployment_package_factory.auth import require_api_token
from deployment_package_factory.api._common import (
    _audit,
    _operator,
    get_business_platform_repository,
)
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import (
    KubernetesRuntimeError,
    disable_business_platform,
    register_business_platform,
)
from deployment_package_factory.services.deployment_packages.models import (
    BusinessPlatformRegistrationRequest,
    BusinessPlatformRegistrationResult,
)

router = APIRouter(
    prefix="/api/deployment-packages",
    tags=["deployment-packages"],
    dependencies=[Depends(require_api_token)],
)


@router.post("/business-platforms/register", response_model=BusinessPlatformRegistrationResult)
async def register_deployment_business_platform(
    payload: BusinessPlatformRegistrationRequest,
    request: Request,
    x_deployment_package_operator: str | None = Header(default=None),
) -> BusinessPlatformRegistrationResult:
    try:
        result = register_business_platform(payload.source_env, payload.key, payload.name, payload.profile)
    except KubernetesRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    platform = get_business_platform_repository().upsert_registered(
        result,
        metadata={"registeredBy": _operator(request, x_deployment_package_operator)},
    )
    _audit(
        request,
        action="business-platform.register",
        status=result.status,
        target_id=result.namespace,
        message="Business platform namespace registered.",
        operator=x_deployment_package_operator,
        metadata=platform.model_dump(by_alias=True),
    )
    return BusinessPlatformRegistrationResult(
        key=result.key,
        name=result.name,
        profile=result.profile,
        namespace=platform.namespace,
        sourceEnv=platform.source_env,
        status=platform.status,
    )


@router.post("/business-platforms/{source_env}/{business_key}/disable", response_model=BusinessPlatformRegistrationResult)
async def disable_deployment_business_platform(
    source_env: str,
    business_key: str,
    request: Request,
    profile: str = "",
    x_deployment_package_operator: str | None = Header(default=None),
) -> BusinessPlatformRegistrationResult:
    try:
        platform = get_business_platform_repository().resolve(source_env, business_key, profile)
        result = disable_business_platform(source_env, business_key, platform.profile)
        platform = get_business_platform_repository().upsert_registered(
            result,
            metadata={**platform.metadata, "disabledBy": _operator(request, x_deployment_package_operator)},
        )
    except KubernetesRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Business platform is not registered.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        request,
        action="business-platform.disable",
        status=result.status,
        target_id=result.namespace,
        message="Business platform namespace disabled.",
        operator=x_deployment_package_operator,
        metadata=platform.model_dump(by_alias=True),
    )
    return BusinessPlatformRegistrationResult(
        key=result.key,
        name=result.name,
        profile=result.profile,
        namespace=platform.namespace,
        sourceEnv=platform.source_env,
        status=platform.status,
    )
