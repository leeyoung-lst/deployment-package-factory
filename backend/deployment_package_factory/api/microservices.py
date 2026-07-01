from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from deployment_package_factory.auth import require_api_token
from deployment_package_factory.api.deployment_packages import (
    _registered_business_platforms,
    get_business_platform_repository,
    get_microservice_repository,
)
from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import RegisteredBusinessPlatform
from deployment_package_factory.services.microservices.delivery import prepare_microservice_delivery, refresh_delivery_status
from deployment_package_factory.services.microservices.scaffold import (
    MicroserviceScaffoldOptions,
    MicroserviceScaffoldRequest,
    MicroserviceScaffoldResult,
    create_microservice_scaffold,
    find_scaffold_artifact,
    find_scaffold_project_root,
    scaffold_options,
)
from deployment_package_factory.services.settings import SystemSettings, create_system_settings_repository
router = APIRouter(
    prefix="/api/microservices",
    tags=["microservices"],
    dependencies=[Depends(require_api_token)],
)


def _output_dir() -> Path:
    return load_settings().data_dir / "microservice-projects"


def _system_settings():
    settings = load_settings()
    if not settings.database_url:
        return SystemSettings()
    return create_system_settings_repository(database_url=settings.database_url).get()


@router.get("/options", response_model=MicroserviceScaffoldOptions)
async def get_microservice_scaffold_options() -> MicroserviceScaffoldOptions:
    return scaffold_options()


@router.post("", response_model=MicroserviceScaffoldResult)
async def register_microservice(payload: MicroserviceScaffoldRequest) -> MicroserviceScaffoldResult:
    try:
        platform = _resolve_business_platform(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Business platform is not registered.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    defaults = _system_settings()
    enriched = payload.model_copy(
        update={
            "business_platform_name": platform.name,
            "business_platform_profile": platform.profile,
            "business_platform_namespace": platform.namespace,
            "k8s_namespace": platform.namespace,
            "git_group": _field_or_default(payload, "git_group", defaults.git.group),
            "image_registry": _field_or_default(payload, "image_registry", defaults.harbor.registry),
            "image_namespace": _field_or_default(payload, "image_namespace", defaults.harbor.project or platform.key),
            "git_base_url": defaults.git.base_url,
            "jenkins_base_url": defaults.jenkins.base_url,
            "jenkins_folder": defaults.jenkins.folder,
        }
    )
    result = create_microservice_scaffold(enriched, output_dir=_output_dir())
    project_root = find_scaffold_project_root(result.project_id, output_dir=_output_dir())
    result.delivery = prepare_microservice_delivery(enriched, result, defaults, project_root)
    get_microservice_repository().upsert(enriched, result)
    return result


def _resolve_business_platform(payload: MicroserviceScaffoldRequest) -> RegisteredBusinessPlatform:
    try:
        return get_business_platform_repository().resolve(
            payload.source_env,
            payload.business_platform_key,
            payload.business_platform_profile,
        )
    except KeyError:
        pass
    for platform in _registered_business_platforms():
        if (
            platform.source_env == payload.source_env
            and platform.key == payload.business_platform_key
            and platform.profile == (payload.business_platform_profile or "")
            and platform.status != "disabled"
        ):
            get_business_platform_repository().upsert_registered(platform)
            return platform
    raise KeyError(payload.business_platform_key)


def _field_or_default(payload: MicroserviceScaffoldRequest, field_name: str, default: str) -> str:
    if field_name in payload.model_fields_set:
        value = str(getattr(payload, field_name)).strip()
        return value or default
    return default


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


@router.post("/{project_id}/delivery/retry", response_model=dict)
async def retry_microservice_delivery(project_id: str) -> dict:
    repo = get_microservice_repository()
    row = repo.get_by_project_id(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Microservice registration not found")
    request = _request_from_registered(row)
    defaults = _system_settings()
    project_root = find_scaffold_project_root(project_id, output_dir=_output_dir())
    delivery = prepare_microservice_delivery(request, _result_stub(row), defaults, project_root)
    updated = repo.update_delivery(project_id, delivery)
    return {"projectId": project_id, "delivery": delivery, "microservice": updated}


@router.get("/{project_id}/delivery/status", response_model=dict)
async def get_microservice_delivery_status(project_id: str) -> dict:
    repo = get_microservice_repository()
    row = repo.get_by_project_id(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Microservice registration not found")
    delivery = refresh_delivery_status(row.get("delivery", {}), _system_settings())
    updated = repo.update_delivery(project_id, delivery)
    return {"projectId": project_id, "delivery": delivery, "microservice": updated}


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


def _request_from_registered(row: dict) -> MicroserviceScaffoldRequest:
    settings = _system_settings()
    return MicroserviceScaffoldRequest(
        serviceKey=row["serviceKey"],
        serviceName=row["serviceName"],
        description=row.get("description", ""),
        projectKind=row.get("projectKind", "backend"),
        techStack=row.get("techStack", "python-fastapi"),
        microFrontendFramework=row.get("microFrontendFramework", ""),
        port=row.get("port", 8000),
        middleware=row.get("middleware", []),
        sourceEnv=row["sourceEnv"],
        businessPlatformKey=row["businessPlatformKey"],
        businessPlatformProfile=row.get("businessPlatformProfile", ""),
        businessPlatformName=row.get("businessPlatformName", ""),
        businessPlatformNamespace=row.get("businessPlatformNamespace", ""),
        gitGroup=row.get("gitGroup", ""),
        imageRegistry=row.get("imageRegistry", ""),
        imageNamespace=row.get("imageNamespace", ""),
        k8sNamespace=row.get("k8sNamespace", ""),
        gitBaseUrl=settings.git.base_url,
        jenkinsBaseUrl=settings.jenkins.base_url,
        jenkinsFolder=settings.jenkins.folder,
    )


def _result_stub(row: dict) -> object:
    class ResultStub:
        project_id = row["projectId"]
        git_repository_url = row.get("gitRepositoryUrl", "")
        jenkins_job = row.get("jenkinsJob", "")

    return ResultStub()
