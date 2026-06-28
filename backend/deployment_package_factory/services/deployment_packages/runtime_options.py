from __future__ import annotations

import os
from dataclasses import dataclass

from deployment_package_factory.services.deployment_packages import builder
from deployment_package_factory.services.deployment_packages.dependency_resolver import resolve_package_preview
from deployment_package_factory.services.deployment_packages.models import DeploymentCatalog, ProjectProfile
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import (
    KubernetesRuntimeError,
    RegisteredBusinessPlatform,
    list_registered_business_platforms,
    source_env_namespaces,
)


@dataclass(frozen=True)
class RuntimeOptions:
    source_envs: list[str]
    platform_services: list[dict]
    business_services: list[dict]
    database_options: list[dict]
    middleware: list[dict]
    projects: list[dict]


def build_runtime_options(catalog: DeploymentCatalog) -> RuntimeOptions:
    env_images: dict[str, list[builder.RuntimeSourceImage]] = {}
    registered_business = _registered_business()
    registered_envs = {item.source_env for item in registered_business if item.source_env}
    for source_env in _candidate_source_envs(registered_envs):
        namespaces = source_env_namespaces(source_env)
        images = builder._list_runtime_images(namespaces) if namespaces else []
        if images or source_env in registered_envs:
            env_images[source_env] = images

    source_envs = sorted(env_images)
    business_options = [_business_option(item) for item in registered_business if item.source_env in env_images]
    platform_options = [
        {
            "key": capability.key,
            "name": capability.name,
            "required": capability.required,
            "namespaceGroup": capability.namespace_group,
            "sourceEnv": source_env,
            "status": "active",
            "registered": True,
        }
        for source_env, runtime_images in env_images.items()
        for capability in catalog.platform.values()
        if _has_runtime_image(capability.images, runtime_images)
    ]
    database_options = [
        {
            "key": option.key,
            "name": option.name,
            "domestic": option.domestic,
            "image": option.image,
            "sourceEnv": source_env,
        }
        for source_env, runtime_images in env_images.items()
        for option in catalog.database_options.values()
        if _has_runtime_image([option.image], runtime_images)
    ]
    middleware_options = [
        {
            "key": option.key,
            "name": option.name,
            "image": option.image,
            "sourceEnv": source_env,
        }
        for source_env, runtime_images in env_images.items()
        for option in catalog.middleware.values()
        if _has_runtime_image([option.image], runtime_images)
    ]
    return RuntimeOptions(
        source_envs=source_envs,
        platform_services=sorted(platform_options, key=lambda item: (item["sourceEnv"], item["key"])),
        business_services=sorted(business_options, key=lambda item: (item["sourceEnv"], item["key"])),
        database_options=sorted(database_options, key=lambda item: (item["sourceEnv"], item["key"])),
        middleware=sorted(middleware_options, key=lambda item: (item["sourceEnv"], item["key"])),
        projects=_runtime_projects(catalog, registered_business, env_images, platform_options, database_options),
    )


def ensure_request_matches_runtime(payload, catalog: DeploymentCatalog) -> None:
    runtime_options = build_runtime_options(catalog)
    if payload.source_env not in runtime_options.source_envs:
        raise ValueError(f"Source environment {payload.source_env!r} was not found in the live Kubernetes environment.")

    active_business = {
        item["key"]
        for item in runtime_options.business_services
        if item.get("sourceEnv") == payload.source_env and item.get("status") != "disabled"
    }
    requested_business = {item.name for item in payload.business_services}
    missing_business = sorted(requested_business - active_business)
    if missing_business:
        raise ValueError(f"Business platform is not registered in source environment {payload.source_env!r}: {missing_business}")

    active_platform = {
        item["key"]
        for item in runtime_options.platform_services
        if item.get("sourceEnv") == payload.source_env and item.get("status") != "disabled"
    }
    requested_platform = set(payload.platform_services)
    missing_platform = sorted(requested_platform - active_platform)
    if missing_platform:
        raise ValueError(f"Platform services are not running in source environment {payload.source_env!r}: {missing_platform}")

    active_databases = {
        item["key"]
        for item in runtime_options.database_options
        if item.get("sourceEnv") == payload.source_env
    }
    if payload.database and payload.database not in active_databases:
        raise ValueError(f"Database {payload.database!r} is not running in source environment {payload.source_env!r}.")

    preview = resolve_package_preview(payload, catalog)
    if preview.database.key not in active_databases:
        raise ValueError(f"Database {preview.database.key!r} is not running in source environment {payload.source_env!r}.")

    resolved_platform = {item.key for item in preview.platform_services}
    missing_resolved_platform = sorted(resolved_platform - active_platform)
    if missing_resolved_platform:
        raise ValueError(
            f"Resolved platform dependencies are not running in source environment {payload.source_env!r}: {missing_resolved_platform}"
        )

    active_middleware = {
        item["key"]
        for item in runtime_options.middleware
        if item.get("sourceEnv") == payload.source_env
    }
    resolved_middleware = {item.key for item in preview.middleware if item.key not in catalog.database_options}
    missing_middleware = sorted(resolved_middleware - active_middleware)
    if missing_middleware:
        raise ValueError(
            f"Resolved middleware dependencies are not running in source environment {payload.source_env!r}: {missing_middleware}"
        )


def _candidate_source_envs(registered_envs: set[str]) -> list[str]:
    configured = os.getenv("DEPLOYMENT_PACKAGE_SOURCE_ENVS", "dev,test")
    values = [item.strip() for item in configured.split(",") if item.strip()]
    values.extend(sorted(registered_envs))
    return list(dict.fromkeys(values))


def _registered_business() -> list[RegisteredBusinessPlatform]:
    try:
        return list_registered_business_platforms()
    except KubernetesRuntimeError:
        return []


def _business_option(item: RegisteredBusinessPlatform) -> dict:
    return {
        "key": item.key,
        "name": item.name,
        "profile": item.profile,
        "namespaceGroup": f"business-{item.key}",
        "namespace": item.namespace,
        "sourceEnv": item.source_env,
        "status": item.status,
        "registered": True,
    }


def _has_runtime_image(catalog_images: list[str], runtime_images: list[builder.RuntimeSourceImage]) -> bool:
    for image in catalog_images:
        for tag in ("prod", "latest", "k8s"):
            if builder._best_runtime_image(builder._with_default_tag(image, tag), runtime_images):
                return True
    return False


def _runtime_projects(
    catalog: DeploymentCatalog,
    registered_business: list[RegisteredBusinessPlatform],
    env_images: dict[str, list[builder.RuntimeSourceImage]],
    platform_options: list[dict],
    database_options: list[dict],
) -> list[dict]:
    projects: list[ProjectProfile] = []
    platform_by_env = _keys_by_env(platform_options)
    database_by_env = _keys_by_env(database_options)
    for business in registered_business:
        if business.status == "disabled" or business.source_env not in env_images:
            continue
        capability = catalog.business.get(business.key)
        if capability is None or not _has_runtime_image(capability.images, env_images[business.source_env]):
            continue
        versions = _image_tags(capability.images, env_images[business.source_env])
        projects.append(
            ProjectProfile(
                key=f"{business.source_env}-{business.key}",
                name=f"{business.name} ({business.source_env})",
                description=f"{business.namespace} 运行环境导出项目",
                defaultVersion=versions[0] if versions else "",
                versions=versions,
                defaultSourceEnv=business.source_env,
                defaultDeployModes=["k8s", "docker-compose"],
                defaultPlatformServices=sorted(platform_by_env.get(business.source_env, set()) & set(capability.depends_on)),
                defaultBusinessServices=[{"name": business.key, "profile": business.profile}],
                defaultDatabase=_default_database(database_by_env.get(business.source_env, set())),
                registry=_dominant_registry(env_images[business.source_env]),
                namespacePrefix=f"{business.key}-prod",
                domain="",
                storageClass="",
                imageTag=versions[0] if versions else "prod",
                overlays=[business.key],
            )
        )
    return [item.model_dump(by_alias=True) for item in sorted(projects, key=lambda item: item.key)]


def _keys_by_env(items: list[dict]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for item in items:
        result.setdefault(item.get("sourceEnv") or "", set()).add(item["key"])
    return result


def _default_database(keys: set[str]) -> str:
    if "postgres" in keys:
        return "postgres"
    if "dm" in keys:
        return "dm"
    return sorted(keys)[0] if keys else ""


def _image_tags(catalog_images: list[str], runtime_images: list[builder.RuntimeSourceImage]) -> list[str]:
    tags: list[str] = []
    for image in catalog_images:
        match = None
        for tag in ("prod", "latest", "k8s"):
            match = builder._best_runtime_image(builder._with_default_tag(image, tag), runtime_images)
            if match:
                break
        if not match:
            continue
        tag = _tag_from_image(match.source_ref)
        if tag:
            tags.append(tag)
    return list(dict.fromkeys(tags))


def _tag_from_image(image: str) -> str:
    image = image.split("@", 1)[0]
    last_part = image.rsplit("/", 1)[-1]
    if ":" not in last_part:
        return ""
    return last_part.rsplit(":", 1)[-1]


def _dominant_registry(images: list[builder.RuntimeSourceImage]) -> str:
    registries: dict[str, int] = {}
    for image in images:
        if not builder._has_registry(image.source_ref):
            continue
        registry = image.source_ref.split("/", 1)[0]
        registries[registry] = registries.get(registry, 0) + 1
    if not registries:
        return ""
    return sorted(registries.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]
