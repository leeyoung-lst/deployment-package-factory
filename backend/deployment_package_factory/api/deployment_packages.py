from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.deployment_packages.builder import PackageBuildError
from deployment_package_factory.services.deployment_packages.catalog import CatalogError, load_catalog
from deployment_package_factory.services.deployment_packages.cleanup import CleanupPolicy, CleanupResult, cleanup_deployment_packages
from deployment_package_factory.services.deployment_packages.dependency_resolver import (
    resolve_package_preview,
)
from deployment_package_factory.services.deployment_packages.models import (
    PackageBuildRequest,
    PackageBuildResult,
    PackagePreview,
    PackagePreviewRequest,
    PackageTask,
)
from deployment_package_factory.services.deployment_packages.task_executor import PackageTaskExecutor, PackageTaskExecutorConfig
from deployment_package_factory.services.deployment_packages.task_repository import PackageTaskRepository

router = APIRouter(prefix="/api/deployment-packages", tags=["deployment-packages"])
_SETTINGS = load_settings()
_TASK_REPO = PackageTaskRepository(_SETTINGS.task_db_path)
_TASK_EXECUTOR = PackageTaskExecutor(
    _TASK_REPO,
    PackageTaskExecutorConfig(
        max_concurrent_builds=_SETTINGS.max_concurrent_builds,
        output_dir=_SETTINGS.output_dir,
        heartbeat_seconds=_SETTINGS.worker_heartbeat_seconds,
        worker_id="api-background",
    ),
)


def get_task_repository() -> PackageTaskRepository:
    return _TASK_REPO


def get_task_executor() -> PackageTaskExecutor:
    return _TASK_EXECUTOR


def should_run_background_tasks() -> bool:
    return _SETTINGS.execution_mode == "background"


@router.get("/options")
async def deployment_package_options() -> dict:
    catalog = load_catalog()
    return {
        "sourceEnvs": ["dev", "test"],
        "deployModes": ["k8s", "docker-compose"],
        "platformServices": [
            {
                "key": item.key,
                "name": item.name,
                "required": item.required,
                "namespaceGroup": item.namespace_group,
            }
            for item in catalog.platform.values()
        ],
        "businessServices": [
            {
                "key": item.key,
                "name": item.name,
                "profile": item.profile,
                "namespaceGroup": item.namespace_group,
            }
            for item in catalog.business.values()
        ],
        "databaseOptions": [
            {
                "key": item.key,
                "name": item.name,
                "domestic": item.domestic,
                "image": item.image,
            }
            for item in catalog.database_options.values()
        ],
        "middleware": [
            {
                "key": item.key,
                "name": item.name,
                "image": item.image,
            }
            for item in catalog.middleware.values()
        ],
        "projects": [
            item.model_dump(by_alias=True)
            for item in catalog.projects.values()
        ],
    }


@router.post("/preview", response_model=PackagePreview)
async def deployment_package_preview(payload: PackagePreviewRequest) -> PackagePreview:
    try:
        return resolve_package_preview(payload, load_catalog())
    except (CatalogError, PackageBuildError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("", response_model=PackageTask)
async def create_deployment_package(payload: PackageBuildRequest, background_tasks: BackgroundTasks) -> PackageTask:
    repo = get_task_repository()
    task = repo.create(payload)
    if should_run_background_tasks():
        background_tasks.add_task(get_task_executor().run, task.task_id, payload)
    return task


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
async def cleanup_deployment_package_outputs(dry_run: bool = False) -> CleanupResult:
    return cleanup_deployment_packages(
        get_task_repository(),
        CleanupPolicy(
            retention_days=_SETTINGS.retention_days,
            max_total_bytes=_SETTINGS.max_total_gb * 1024 * 1024 * 1024,
            dry_run=dry_run,
        ),
    )


@router.post("/tasks/{task_id}/cancel", response_model=PackageTask)
async def cancel_deployment_package_task(task_id: str) -> PackageTask:
    try:
        return get_task_repository().cancel(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment package task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/retry", response_model=PackageTask)
async def retry_deployment_package_task(task_id: str, background_tasks: BackgroundTasks) -> PackageTask:
    repo = get_task_repository()
    try:
        retry_task = repo.retry(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment package task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
async def download_deployment_package(package_id: str) -> FileResponse:
    task = _find_completed_task(package_id)
    if task is None or task.result is None:
        raise HTTPException(status_code=404, detail="Deployment package task not found")
    artifact = Path(task.result.artifact_path)
    if not artifact.exists():
        raise HTTPException(status_code=404, detail="Deployment package artifact not found")
    return FileResponse(
        artifact,
        media_type="application/gzip",
        filename=artifact.name,
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
