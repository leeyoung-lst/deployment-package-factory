from __future__ import annotations

from pathlib import Path

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from deployment_package_factory.auth import require_api_token
from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.deployment_packages.builder import PackageBuildError, check_image_export_environment
from deployment_package_factory.services.deployment_packages import builder as package_builder
from deployment_package_factory.services.deployment_packages.catalog import CatalogError, load_catalog
from deployment_package_factory.services.deployment_packages.cleanup import CleanupPolicy, CleanupResult, cleanup_deployment_packages
from deployment_package_factory.services.deployment_packages.dependency_resolver import (
    resolve_package_preview,
)
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import (
    KubernetesRuntimeError,
    RegisteredBusinessPlatform,
    disable_business_platform,
    list_registered_business_platforms,
    register_business_platform,
)
from deployment_package_factory.services.deployment_packages.models import (
    AuditEvent,
    BusinessPlatformRegistrationRequest,
    BusinessPlatformRegistrationResult,
    ImageExportEnvironmentCheck,
    PackageBuildRequest,
    PackageBuildResult,
    PackagePreview,
    PackagePreviewRequest,
    PackageTask,
)
from deployment_package_factory.services.deployment_packages.repositories import create_audit_repository, create_task_repository
from deployment_package_factory.services.deployment_packages.repositories import create_business_platform_repository
from deployment_package_factory.services.deployment_packages.runtime_options import build_runtime_options, ensure_request_matches_runtime
from deployment_package_factory.services.deployment_packages.task_executor import PackageTaskExecutor, PackageTaskExecutorConfig

LOGGER = logging.getLogger(__name__)
DOWNLOAD_CHUNK_SIZE = 1024 * 1024

router = APIRouter(
    prefix="/api/deployment-packages",
    tags=["deployment-packages"],
    dependencies=[Depends(require_api_token)],
)
_SETTINGS = load_settings()
_TASK_REPO = create_task_repository(database_url=_SETTINGS.database_url, sqlite_path=_SETTINGS.task_db_path)
_AUDIT_REPO = create_audit_repository(database_url=_SETTINGS.database_url, sqlite_path=_SETTINGS.audit_db_path)
_BUSINESS_PLATFORM_REPO = create_business_platform_repository(
    database_url=_SETTINGS.database_url,
    sqlite_path=_SETTINGS.business_platform_db_path,
)
_TASK_EXECUTOR = PackageTaskExecutor(
    _TASK_REPO,
    PackageTaskExecutorConfig(
        max_concurrent_builds=_SETTINGS.max_concurrent_builds,
        output_dir=_SETTINGS.output_dir,
        heartbeat_seconds=_SETTINGS.worker_heartbeat_seconds,
        worker_id="api-background",
    ),
)


def get_task_repository():
    return _TASK_REPO


def get_audit_repository():
    return _AUDIT_REPO


def get_business_platform_repository():
    return _BUSINESS_PLATFORM_REPO


def get_task_executor() -> PackageTaskExecutor:
    return _TASK_EXECUTOR


def should_run_background_tasks() -> bool:
    return _SETTINGS.execution_mode == "background"


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
        "projects": runtime_options.projects,
    }


@router.post("/preview", response_model=PackagePreview)
async def deployment_package_preview(payload: PackagePreviewRequest) -> PackagePreview:
    try:
        catalog = load_catalog()
        preview = resolve_package_preview(payload, catalog)
        registered_business = _registered_business_platforms()
        ensure_request_matches_runtime(payload, catalog, registered_business)
        request, project = package_builder._apply_project_build_defaults(PackageBuildRequest.model_validate(payload.model_dump(by_alias=True)), catalog)
        image_tag = project.image_tag if project else "prod"
        runtime_images = package_builder._discover_runtime_source_images(
            request.source_env,
            preview.images,
            image_tag,
            _request_business_namespaces(request, registered_business),
        )
        image_entries = package_builder._image_entries(preview.images, request, image_tag, runtime_images, require_runtime_sources=bool(runtime_images))
        return preview.model_copy(update={"image_entries": image_entries})
    except (CatalogError, PackageBuildError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.get("/image-export-environment", response_model=ImageExportEnvironmentCheck)
async def image_export_environment() -> ImageExportEnvironmentCheck:
    return check_image_export_environment()


@router.post("", response_model=PackageTask)
async def create_deployment_package(
    payload: PackageBuildRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    x_deployment_package_operator: str | None = Header(default=None),
) -> PackageTask:
    try:
        ensure_request_matches_runtime(payload, load_catalog(), _registered_business_platforms())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    repo = get_task_repository()
    task = repo.create(payload)
    _audit(
        request,
        action="package.create",
        status="accepted",
        target_id=task.task_id,
        message="Deployment package task created.",
        operator=x_deployment_package_operator,
        metadata={
            "projectKey": payload.project_key,
            "sourceEnv": payload.source_env,
            "deployModes": payload.deploy_modes,
            "businessServices": [item.model_dump() for item in payload.business_services],
            "database": payload.database,
            "imageMode": payload.image_mode,
        },
    )
    if should_run_background_tasks():
        background_tasks.add_task(get_task_executor().run, task.task_id, payload)
    return task


@router.get("/audit-events", response_model=list[AuditEvent])
async def list_deployment_package_audit_events(limit: int = 100) -> list[AuditEvent]:
    return get_audit_repository().list(limit=limit)


@router.get("/tasks", response_model=list[PackageTask])
async def list_deployment_package_tasks(limit: int = 50) -> list[PackageTask]:
    return get_task_repository().list(limit=limit)


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
    result = cleanup_deployment_packages(
        get_task_repository(),
        CleanupPolicy(
            retention_days=_SETTINGS.retention_days,
            max_total_bytes=_SETTINGS.max_total_gb * 1024 * 1024 * 1024,
            dry_run=dry_run,
        ),
    )
    _audit(
        request,
        action="package.cleanup",
        status="dry-run" if dry_run else "completed",
        message="Deployment package cleanup executed.",
        operator=x_deployment_package_operator,
        metadata=result.model_dump(by_alias=True),
    )
    return result


@router.post("/tasks/{task_id}/cancel", response_model=PackageTask)
async def cancel_deployment_package_task(
    task_id: str,
    request: Request,
    x_deployment_package_operator: str | None = Header(default=None),
) -> PackageTask:
    try:
        task = get_task_repository().cancel(task_id)
        _audit(
            request,
            action="task.cancel",
            status=task.status,
            target_id=task_id,
            message=task.message,
            operator=x_deployment_package_operator,
        )
        return task
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment package task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/retry", response_model=PackageTask)
async def retry_deployment_package_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
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
        request,
        action="task.retry",
        status="accepted",
        target_id=retry_task.task_id,
        message=f"Retry task created from {task_id}.",
        operator=x_deployment_package_operator,
        metadata={"sourceTaskId": task_id},
    )
    if should_run_background_tasks():
        background_tasks.add_task(get_task_executor().run, retry_task.task_id, PackageBuildRequest.model_validate(retry_task.request))
    return retry_task


@router.get("/{package_id}", response_model=PackageBuildResult)
async def get_deployment_package(package_id: str) -> PackageBuildResult:
    task = _find_completed_task(package_id)
    if task is None or task.result is None:
        raise HTTPException(status_code=404, detail="Deployment package task not found")
    return task.result


@router.get("/{package_id}/download")
async def download_deployment_package(
    package_id: str,
    request: Request,
    x_deployment_package_operator: str | None = Header(default=None),
) -> StreamingResponse:
    task = _find_completed_task(package_id)
    if task is None or task.result is None:
        raise HTTPException(status_code=404, detail="Deployment package task not found")
    artifact = Path(task.result.artifact_path)
    if not artifact.exists():
        raise HTTPException(status_code=404, detail="Deployment package artifact not found")
    _audit(
        request,
        action="package.download",
        status="completed",
        target_id=task.result.package_id,
        message="Deployment package downloaded.",
        operator=x_deployment_package_operator,
        metadata={"taskId": task.task_id, "artifactPath": task.result.artifact_path},
    )
    file_size = artifact.stat().st_size
    return StreamingResponse(
        _iter_file_chunks(artifact),
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.name}"',
            "Content-Length": str(file_size),
            "X-Deployment-Package-Sha256": task.result.sha256,
        },
    )


@router.get("/{package_id}/checksum")
async def download_deployment_package_checksum(
    package_id: str,
    request: Request,
    x_deployment_package_operator: str | None = Header(default=None),
) -> FileResponse:
    task = _find_completed_task(package_id)
    if task is None or task.result is None:
        raise HTTPException(status_code=404, detail="Deployment package task not found")
    checksum = _checksum_path(task.result)
    if not checksum.exists():
        raise HTTPException(status_code=404, detail="Deployment package checksum not found")
    _audit(
        request,
        action="package.checksum.download",
        status="completed",
        target_id=task.result.package_id,
        message="Deployment package checksum downloaded.",
        operator=x_deployment_package_operator,
        metadata={"taskId": task.task_id, "checksumPath": str(checksum)},
    )
    return FileResponse(
        checksum,
        media_type="text/plain",
        filename=checksum.name,
        headers={"X-Deployment-Package-Sha256": task.result.sha256},
    )


def _find_completed_task(package_or_task_id: str) -> PackageTask | None:
    repo = get_task_repository()
    task = repo.get(package_or_task_id)
    if task and task.status == "completed":
        return task
    for candidate in repo.list(limit=500):
        if candidate.result and candidate.result.package_id == package_or_task_id and candidate.status == "completed":
            return candidate
    return None


def _checksum_path(result: PackageBuildResult) -> Path:
    if result.checksum_path:
        return Path(result.checksum_path)
    artifact = Path(result.artifact_path)
    return artifact.with_name(f"{artifact.name}.sha256")


def _iter_file_chunks(path: Path, chunk_size: int = DOWNLOAD_CHUNK_SIZE):
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            yield chunk


def _registered_business_platforms() -> list[RegisteredBusinessPlatform]:
    platforms = [
        RegisteredBusinessPlatform(
            key=item.key,
            name=item.name,
            profile=item.profile,
            namespace=item.namespace,
            source_env=item.source_env,
            status=item.status,
        )
        for item in get_business_platform_repository().list(include_disabled=True)
    ]
    existing_keys = {(item.source_env, item.key, item.profile) for item in platforms}
    try:
        for item in list_registered_business_platforms(include_disabled=True):
            key = (item.source_env, item.key, item.profile)
            if key not in existing_keys:
                platforms.append(item)
                existing_keys.add(key)
    except KubernetesRuntimeError as exc:
        LOGGER.warning("Failed to discover business platforms from Kubernetes namespaces: %s", exc)
    return sorted(platforms, key=lambda item: (item.source_env, item.key, item.profile, item.namespace))


def _request_business_namespaces(request: PackageBuildRequest, platforms: list[RegisteredBusinessPlatform]) -> list[str]:
    namespaces: list[str] = []
    for selection in request.business_services:
        for platform in platforms:
            if (
                platform.source_env == request.source_env
                and platform.key == selection.name
                and platform.profile == (selection.profile or "")
                and platform.status != "disabled"
            ):
                namespaces.append(platform.namespace)
    return list(dict.fromkeys(namespaces))


def _audit(
    request: Request,
    *,
    action: str,
    status: str,
    target_id: str = "",
    message: str = "",
    operator: str | None = None,
    metadata: dict | None = None,
) -> None:
    try:
        get_audit_repository().record(
            action=action,
            status=status,
            target_id=target_id,
            operator=_operator(request, operator),
            client_ip=_client_ip(request),
            message=message,
            metadata=metadata or {},
        )
    except Exception as exc:  # pragma: no cover - audit must not break package operations
        LOGGER.warning("Failed to record deployment package audit event: %s", exc)


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
