from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from deployment_package_factory.services.deployment_packages.builder import PackageBuildError, build_deployment_package
from deployment_package_factory.services.deployment_packages.catalog import CatalogError, load_catalog
from deployment_package_factory.services.deployment_packages.dependency_resolver import (
    resolve_package_preview,
)
from deployment_package_factory.services.deployment_packages.models import (
    PackageBuildRequest,
    PackageBuildResult,
    PackagePreview,
    PackagePreviewRequest,
)

router = APIRouter(prefix="/api/deployment-packages", tags=["deployment-packages"])
_TASKS: dict[str, PackageBuildResult] = {}


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
    }


@router.post("/preview", response_model=PackagePreview)
async def deployment_package_preview(payload: PackagePreviewRequest) -> PackagePreview:
    try:
        return resolve_package_preview(payload, load_catalog())
    except (CatalogError, PackageBuildError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("", response_model=PackageBuildResult)
async def create_deployment_package(payload: PackageBuildRequest) -> PackageBuildResult:
    try:
        result = build_deployment_package(payload)
    except (CatalogError, PackageBuildError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _TASKS[result.package_id] = result
    return result


@router.get("/{package_id}", response_model=PackageBuildResult)
async def get_deployment_package(package_id: str) -> PackageBuildResult:
    result = _TASKS.get(package_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Deployment package task not found")
    return result


@router.get("/{package_id}/download")
async def download_deployment_package(package_id: str) -> FileResponse:
    result = _TASKS.get(package_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Deployment package task not found")
    artifact = Path(result.artifact_path)
    if not artifact.exists():
        raise HTTPException(status_code=404, detail="Deployment package artifact not found")
    return FileResponse(
        artifact,
        media_type="application/gzip",
        filename=artifact.name,
    )
