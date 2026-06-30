from __future__ import annotations

from email.utils import formatdate
from pathlib import Path

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from deployment_package_factory.auth import require_api_token
from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.deployment_packages.builder import PackageBuildError, check_image_export_environment
from deployment_package_factory.services.deployment_packages import builder as package_builder
from deployment_package_factory.services.deployment_packages.catalog import CatalogError, load_catalog
from deployment_package_factory.services.deployment_packages.cleanup import CleanupPolicy, CleanupResult, cleanup_deployment_packages
from deployment_package_factory.services.deployment_packages.dependency_resolver import (
    resolve_package_preview,
)
from deployment_package_factory.services.deployment_packages.download_scripts import render_download_script
from deployment_package_factory.services.deployment_packages.download_streaming import DownloadMetadata, InvalidRangeError, iter_file_chunks, parse_range_header, should_ignore_range
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
from deployment_package_factory.services.deployment_packages.microservice_delivery import microservice_delivery_not_ready_error
from deployment_package_factory.services.deployment_packages.repositories import create_audit_repository, create_task_repository
from deployment_package_factory.services.deployment_packages.repositories import create_business_platform_repository
from deployment_package_factory.services.deployment_packages.runtime_options import build_runtime_options, ensure_request_matches_runtime, with_runtime_projects
from deployment_package_factory.services.deployment_packages.task_executor import PackageTaskExecutor, PackageTaskExecutorConfig
from deployment_package_factory.services.microservices.repository import create_microservice_repository

LOGGER = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/deployment-packages",
    tags=["deployment-packages"],
    dependencies=[Depends(require_api_token)],
)
_SETTINGS = load_settings()
_TASK_REPO = None
_AUDIT_REPO = None
_BUSINESS_PLATFORM_REPO = None
_MICROSERVICE_REPO = None
_TASK_EXECUTOR = None


def get_task_repository():
    global _TASK_REPO
    if _TASK_REPO is None:
        _TASK_REPO = create_task_repository(database_url=_SETTINGS.database_url)
    return _TASK_REPO


def get_audit_repository():
    global _AUDIT_REPO
    if _AUDIT_REPO is None:
        _AUDIT_REPO = create_audit_repository(database_url=_SETTINGS.database_url)
    return _AUDIT_REPO


def get_business_platform_repository():
    global _BUSINESS_PLATFORM_REPO
    if _BUSINESS_PLATFORM_REPO is None:
        _BUSINESS_PLATFORM_REPO = create_business_platform_repository(database_url=_SETTINGS.database_url)
    return _BUSINESS_PLATFORM_REPO


def get_microservice_repository():
    global _MICROSERVICE_REPO
    if _MICROSERVICE_REPO is None:
        _MICROSERVICE_REPO = create_microservice_repository(database_url=_SETTINGS.database_url)
    return _MICROSERVICE_REPO


def get_task_executor() -> PackageTaskExecutor:
    global _TASK_EXECUTOR
    if _TASK_EXECUTOR is None:
        _TASK_EXECUTOR = PackageTaskExecutor(
            get_task_repository(),
            PackageTaskExecutorConfig(
                max_concurrent_builds=_SETTINGS.max_concurrent_builds,
                output_dir=_SETTINGS.output_dir,
                heartbeat_seconds=_SETTINGS.worker_heartbeat_seconds,
                worker_id="api-background",
            ),
        )
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
        request, project = package_builder._apply_project_build_defaults(PackageBuildRequest.model_validate(payload.model_dump(by_alias=True)), catalog)
        image_tag = project.image_tag if project else "prod"
        business_namespaces = _request_business_namespaces(request, registered_business)
        registered_microservices = _request_microservices(request)
        runtime_business_images = package_builder._discover_runtime_business_images(request.source_env, business_namespaces)
        preview = package_builder._preview_with_runtime_business_images(preview, runtime_business_images)
        preview = package_builder._preview_with_registered_microservices(preview, registered_microservices)
        runtime_images = package_builder._discover_runtime_source_images(
            request.source_env,
            preview.images,
            image_tag,
            business_namespaces,
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
    payload = payload.normalized_for_create()
    try:
        registered_business = _registered_business_platforms()
        ensure_request_matches_runtime(payload, with_runtime_projects(load_catalog(), registered_business), registered_business)
        delivery_error = microservice_delivery_not_ready_error(_request_microservices(payload))
        if delivery_error["services"]:
            _audit_package_create_blocked(request, payload, delivery_error, x_deployment_package_operator)
            raise HTTPException(status_code=400, detail=delivery_error)
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
async def list_deployment_package_audit_events(
    limit: int = 100,
    status: str = "",
    action: str = "",
    action_prefix: str = Query(default="", alias="actionPrefix"),
) -> list[AuditEvent]:
    return get_audit_repository().list(limit=limit, status=status, action=action, action_prefix=action_prefix)


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
    range_header: str | None = Header(default=None, alias="Range"),
    if_range: str | None = Header(default=None, alias="If-Range"),
    x_deployment_package_operator: str | None = Header(default=None),
) -> StreamingResponse:
    task, artifact = _completed_artifact(package_id)
    _audit(
        request,
        action="package.download",
        status="completed",
        target_id=task.result.package_id,
        message="Deployment package downloaded.",
        operator=x_deployment_package_operator,
        metadata={"taskId": task.task_id, "artifactPath": task.result.artifact_path},
    )
    metadata = _download_metadata(task.result, artifact)
    active_range = "" if should_ignore_range(if_range or "", metadata) else (range_header or "")
    try:
        download_range = parse_range_header(active_range, metadata.size)
    except InvalidRangeError as exc:
        raise HTTPException(status_code=416, detail=str(exc), headers={"Content-Range": f"bytes */{metadata.size}"}) from exc
    headers = {**metadata.headers, "Content-Length": str(download_range.length if download_range else metadata.size)}
    if download_range:
        headers["Content-Range"] = download_range.content_range
    return StreamingResponse(
        iter_file_chunks(artifact, start=download_range.start, end=download_range.end) if download_range else iter_file_chunks(artifact),
        media_type="application/gzip",
        status_code=206 if download_range else 200,
        headers=headers,
    )


@router.head("/{package_id}/download")
async def head_deployment_package_download(package_id: str) -> Response:
    task, artifact = _completed_artifact(package_id)
    return Response(status_code=200, headers=_download_metadata(task.result, artifact).headers)


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


@router.get("/{package_id}/download-script.ps1")
async def download_deployment_package_powershell_script(
    package_id: str,
    request: Request,
    deployment_package_token: str = Query(default=""),
) -> Response:
    task, artifact = _completed_artifact(package_id)
    metadata = _download_metadata(task.result, artifact)
    content = render_download_script(task.result.package_id, task.result.sha256, shell="powershell", size=metadata.size, etag=metadata.etag, base_url=_package_base_url(request), token=deployment_package_token)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{task.result.package_id}-download.ps1"'},
    )


@router.get("/{package_id}/download-script.sh")
async def download_deployment_package_shell_script(
    package_id: str,
    request: Request,
    deployment_package_token: str = Query(default=""),
) -> Response:
    task, artifact = _completed_artifact(package_id)
    metadata = _download_metadata(task.result, artifact)
    content = render_download_script(task.result.package_id, task.result.sha256, shell="bash", size=metadata.size, etag=metadata.etag, base_url=_package_base_url(request), token=deployment_package_token)
    return Response(
        content=content,
        media_type="text/x-shellscript; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{task.result.package_id}-download.sh"'},
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


def _package_base_url(request: Request) -> str:
    return str(request.url_for("deployment_package_options")).rsplit("/options", 1)[0]


def _completed_artifact(package_id: str) -> tuple[PackageTask, Path]:
    task = _find_completed_task(package_id)
    if task is None or task.result is None:
        raise HTTPException(status_code=404, detail="Deployment package task not found")
    artifact = Path(task.result.artifact_path)
    if not artifact.exists():
        raise HTTPException(status_code=404, detail="Deployment package artifact not found")
    return task, artifact


def _download_metadata(result: PackageBuildResult, artifact: Path) -> DownloadMetadata:
    stat = artifact.stat()
    return DownloadMetadata(
        filename=artifact.name,
        size=stat.st_size,
        sha256=result.sha256,
        etag=f'"{result.sha256}"',
        last_modified=formatdate(stat.st_mtime, usegmt=True),
    )


def _checksum_path(result: PackageBuildResult) -> Path:
    if result.checksum_path:
        return Path(result.checksum_path)
    artifact = Path(result.artifact_path)
    return artifact.with_name(f"{artifact.name}.sha256")


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


def _request_microservices(request: PackageBuildRequest) -> list[dict]:
    services: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for selection in request.business_services:
        if not selection.name:
            continue
        for service in get_microservice_repository().list(
            source_env=request.source_env,
            business_platform_key=selection.name,
            business_platform_profile=selection.profile or "",
        ):
            key = (
                str(service.get("sourceEnv") or ""),
                str(service.get("businessPlatformKey") or ""),
                str(service.get("businessPlatformProfile") or ""),
                str(service.get("serviceKey") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            services.append(service)
    return services


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


def _audit_package_create_blocked(
    request: Request,
    payload: PackageBuildRequest,
    delivery_error: dict[str, object],
    operator: str | None,
) -> None:
    _audit(
        request,
        action="package.create.blocked",
        status="blocked",
        message=str(delivery_error["message"]),
        operator=operator,
        metadata={
            "code": delivery_error["code"],
            "projectKey": payload.project_key,
            "sourceEnv": payload.source_env,
            "businessServices": [item.model_dump() for item in payload.business_services],
            "services": delivery_error["services"],
        },
    )


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
