from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from deployment_package_factory.auth import require_api_token
from deployment_package_factory.api.deployment_packages import get_business_platform_repository, get_microservice_repository
from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.microservices.scaffold import (
    MicroserviceScaffoldOptions,
    MicroserviceScaffoldRequest,
    MicroserviceScaffoldResult,
    create_microservice_scaffold,
    find_scaffold_artifact,
    scaffold_options,
)
router = APIRouter(
    prefix="/api/microservices",
    tags=["microservices"],
    dependencies=[Depends(require_api_token)],
)


def _output_dir() -> Path:
    return load_settings().data_dir / "microservice-projects"


@router.get("/options", response_model=MicroserviceScaffoldOptions)
async def get_microservice_scaffold_options() -> MicroserviceScaffoldOptions:
    return scaffold_options()


@router.post("", response_model=MicroserviceScaffoldResult)
async def register_microservice(payload: MicroserviceScaffoldRequest) -> MicroserviceScaffoldResult:
    try:
        platform = get_business_platform_repository().resolve(
            payload.source_env,
            payload.business_platform_key,
            payload.business_platform_profile,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Business platform is not registered.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    enriched = payload.model_copy(
        update={
            "business_platform_name": platform.name,
            "business_platform_profile": platform.profile,
            "business_platform_namespace": platform.namespace,
            "k8s_namespace": payload.k8s_namespace or platform.namespace,
            "image_namespace": payload.image_namespace or platform.key,
        }
    )
    result = create_microservice_scaffold(enriched, output_dir=_output_dir())
    get_microservice_repository().upsert(enriched, result)
    return result


@router.get("")
async def list_microservices(
    source_env: str | None = None,
    business_platform_key: str | None = None,
    business_platform_profile: str | None = None,
) -> list[dict]:
    return get_microservice_repository().list(
        source_env=source_env,
        business_platform_key=business_platform_key,
        business_platform_profile=business_platform_profile,
    )


@router.get("/{project_id}/download")
async def download_microservice_scaffold(project_id: str) -> FileResponse:
    artifact = find_scaffold_artifact(project_id, output_dir=_output_dir())
    if artifact is None or not artifact.exists():
        raise HTTPException(status_code=404, detail="Microservice scaffold artifact not found")
    return FileResponse(
        artifact,
        media_type="application/gzip",
        filename=artifact.name,
    )
