"""Deployment package creation, task management API routes.

Shared singletons and helpers live in ``api._common``.
Business-platform routes live in ``api.business_platforms``.
Download/checksum/script routes live in ``api.downloads``.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request

from deployment_package_factory.auth import require_api_token
from deployment_package_factory.api._common import (
    _audit,
    get_audit_repository,
    get_microservice_repository,
    get_settings,
    get_task_executor,
    get_task_repository,
    should_run_background_tasks,
)
from deployment_package_factory.services.deployment_packages.builder import PackageBuildError, check_image_export_environment
from deployment_package_factory.services.deployment_packages import builder as package_builder
from deployment_package_factory.services.deployment_packages.runtime_resources import build_runtime_config, public_runtime_config
from deployment_package_factory.services.deployment_packages.catalog import CatalogError, load_catalog
from deployment_package_factory.services.deployment_packages.cleanup import CleanupPolicy, CleanupResult, cleanup_deployment_packages
from deployment_package_factory.services.deployment_packages.dependency_resolver import resolve_package_preview
from deployment_package_factory.services.deployment_packages.microservice_delivery import microservice_delivery_not_ready_error
from deployment_package_factory.services.deployment_packages.models import (
    AuditEvent,
    ImageExportEnvironmentCheck,
    PackageBuildRequest,
    PackagePreview,
    PackagePreviewRequest,
    PackageTask,
)
from deployment_package_factory.services.deployment_packages.runtime_options import build_runtime_options, ensure_request_matches_runtime, with_runtime_projects
from deployment_package_factory.api._common import _registered_business_platforms, request_business_namespaces, request_microservices

LOGGER = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/deployment-packages",
    tags=["deployment-packages"],
    dependencies=[Depends(require_api_token)],
)


# -- options / preview -------------------------------------------------------


@router.get("/options")
async def deployment_package_options() -> dict:
    catalog = load_catalog()
    runtime_options = build_runtime_options(catalog, _registered_business_platforms())
    return {
        "sourceEnvs": runtime_options.source_envs,
        "deployModes": ["k8s", "docker-compose"],
        "platformServices": runtime_options.platform_services,
        "businessServices": runtime_options.business_services,
        "databaseOptions": runtime_options.database_options,
        "middleware": runtime_options.middleware,
        "microservices": get_microservice_repository().list(),
        "projects": runtime_options.projects,
    }


@router.post("/preview", response_model=PackagePreview)
async def deployment_package_preview(payload: PackagePreviewRequest) -> PackagePreview:
    try:
        registered_business = _registered_business_platforms()
        catalog = with_runtime_projects(load_catalog(), registered_business)
        preview = resolve_package_preview(payload, catalog)
        ensure_request_matches_runtime(payload, catalog, registered_business)
        request, project = package_builder._apply_project_build_defaults(
            PackageBuildRequest.model_validate(payload.model_dump(by_alias=True)), catalog,
        )
        image_tag = project.image_tag if project else "prod"
        business_namespaces = request_business_namespaces(request, registered_business)
        registered_microservices = request_microservices(request)
        runtime_business_images = package_builder._discover_runtime_business_images(request.source_env, business_namespaces)
        preview = package_builder._preview_with_runtime_business_images(preview, runtime_business_images)
        preview = package_builder._preview_with_registered_microservices(preview, registered_microservices)
        runtime_images = package_builder._discover_runtime_source_images(
            request.source_env, preview.images, image_tag, business_namespaces,
        )
        image_entries = package_builder._image_entries(
            preview.images, request, image_tag, runtime_images, require_runtime_sources=bool(runtime_images),
        )
        middleware_config = package_builder._middleware_config(request, preview)
        runtime_env = package_builder._resolve_runtime_env(request.source_env, middleware_config, business_namespaces)
        runtime_env.update(request.runtime_config_overrides)
        runtime_config = build_runtime_config(
            request=request, preview=preview, middleware_config=middleware_config,
            runtime_env=runtime_env, probes=package_builder._runtime_env_probes(request.source_env, business_namespaces),
        )
        return preview.model_copy(
            update={
                "image_entries": image_entries,
                "runtime_config": public_runtime_config(runtime_config, include_values=True),
            }
        )
    except (CatalogError, PackageBuildError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/image-export-environment", response_model=ImageExportEnvironmentCheck)
async def image_export_environment() -> ImageExportEnvironmentCheck:
    return check_image_export_environment()


# -- create / tasks ----------------------------------------------------------


@router.post("", response_model=PackageTask)
async def create_deployment_package(
    payload: PackageBuildRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    x_deployment_package_operator: str | None = Header(default=None),
) -> PackageTask:
    payload = payload.normalized_for_create()
    try:
        registered_business = _registered_business_platforms()
        ensure_request_matches_runtime(payload, with_runtime_projects(load_catalog(), registered_business), registered_business)
        delivery_error = microservice_delivery_not_ready_error(request_microservices(payload))
        if delivery_error["services"]:
            _audit_package_create_blocked(request, payload, delivery_error, x_deployment_package_operator)
            raise HTTPException(status_code=400, detail=delivery_error)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    repo = get_task_repository()
    task = repo.create(payload)
    _audit(
        request, action="package.create", status="accepted", target_id=task.task_id,
        message="Deployment package task created.", operator=x_deployment_package_operator,
        metadata={
            "projectKey": payload.project_key, "sourceEnv": payload.source_env,
            "deployModes": payload.deploy_modes,
            "businessServices": [item.model_dump() for item in payload.business_services],
            "database": payload.database, "imageMode": payload.image_mode,
        },
    )
    if should_run_background_tasks():
        background_tasks.add_task(get_task_executor().run, task.task_id, payload)
    return task


@router.get("/audit-events", response_model=list[AuditEvent])
async def list_deployment_package_audit_events(
    limit: int = 100,
    status: str = "",
    action: str = "",
    action_prefix: str = Query(default="", alias="actionPrefix"),
) -> list[AuditEvent]:
    return get_audit_repository().list(limit=min(max(1, limit), 1000), status=status, action=action, action_prefix=action_prefix)


@router.get("/tasks", response_model=list[PackageTask])
async def list_deployment_package_tasks(limit: int = 50) -> list[PackageTask]:
    return get_task_repository().list(limit=min(max(1, limit), 500))


@router.get("/tasks/{task_id}", response_model=PackageTask)
async def get_deployment_package_task(task_id: str) -> PackageTask:
    task = get_task_repository().get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Deployment package task not found")
    return task


@router.post("/cleanup", response_model=CleanupResult)
async def cleanup_deployment_package_outputs(
    request: Request,
    dry_run: bool = False,
    x_deployment_package_operator: str | None = Header(default=None),
) -> CleanupResult:
    settings = get_settings()
    result = cleanup_deployment_packages(
        get_task_repository(),
        CleanupPolicy(
            retention_days=settings.retention_days,
            max_total_bytes=settings.max_total_gb * 1024 * 1024 * 1024,
            dry_run=dry_run,
        ),
    )
    _audit(
        request, action="package.cleanup", status="dry-run" if dry_run else "completed",
        message="Deployment package cleanup executed.", operator=x_deployment_package_operator,
        metadata=result.model_dump(by_alias=True),
    )
    return result


@router.post("/tasks/{task_id}/cancel", response_model=PackageTask)
async def cancel_deployment_package_task(
    task_id: str, request: Request, x_deployment_package_operator: str | None = Header(default=None),
) -> PackageTask:
    try:
        task = get_task_repository().cancel(task_id)
        _audit(
            request, action="task.cancel", status=task.status, target_id=task_id,
            message=task.message, operator=x_deployment_package_operator,
        )
        return task
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment package task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/retry", response_model=PackageTask)
async def retry_deployment_package_task(
    task_id: str, background_tasks: BackgroundTasks, request: Request,
    x_deployment_package_operator: str | None = Header(default=None),
) -> PackageTask:
    repo = get_task_repository()
    try:
        retry_task = repo.retry(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment package task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        request, action="task.retry", status="accepted", target_id=retry_task.task_id,
        message=f"Retry task created from {task_id}.", operator=x_deployment_package_operator,
        metadata={"sourceTaskId": task_id},
    )
    if should_run_background_tasks():
        background_tasks.add_task(get_task_executor().run, retry_task.task_id, PackageBuildRequest.model_validate(retry_task.request))
    return retry_task


def _audit_package_create_blocked(request, payload, delivery_error, operator):
    _audit(
        request, action="package.create.blocked", status="blocked",
        message=str(delivery_error["message"]), operator=operator,
        metadata={
            "code": delivery_error["code"], "projectKey": payload.project_key,
            "sourceEnv": payload.source_env,
            "businessServices": [item.model_dump() for item in payload.business_services],
            "services": delivery_error["services"],
        },
    )

