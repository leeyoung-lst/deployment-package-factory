"""Shared singletons, locks, and helper functions for API modules.

This module breaks the dependency cycle between deployment_packages,
business_platforms, and microservices API routers.
"""
from __future__ import annotations

import threading
from pathlib import Path

import logging

from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.deployment_packages.kubernetes_runtime import (
    KubernetesRuntimeError,
    RegisteredBusinessPlatform,
    list_registered_business_platforms,
)
from deployment_package_factory.services.deployment_packages.repositories import (
    create_audit_repository,
    create_business_platform_repository,
    create_task_repository,
)
from deployment_package_factory.services.microservices.repository import create_microservice_repository

LOGGER = logging.getLogger(__name__)

_SETTINGS = load_settings()
_TASK_REPO = None
_AUDIT_REPO = None
_BUSINESS_PLATFORM_REPO = None
_MICROSERVICE_REPO = None
_TASK_EXECUTOR = None
_REPO_LOCK = threading.Lock()


def get_task_repository():
    global _TASK_REPO
    with _REPO_LOCK:
        if _TASK_REPO is None:
            _TASK_REPO = create_task_repository(database_url=_SETTINGS.database_url)
        return _TASK_REPO


def get_audit_repository():
    global _AUDIT_REPO
    with _REPO_LOCK:
        if _AUDIT_REPO is None:
            _AUDIT_REPO = create_audit_repository(database_url=_SETTINGS.database_url)
        return _AUDIT_REPO


def get_business_platform_repository():
    global _BUSINESS_PLATFORM_REPO
    with _REPO_LOCK:
        if _BUSINESS_PLATFORM_REPO is None:
            _BUSINESS_PLATFORM_REPO = create_business_platform_repository(database_url=_SETTINGS.database_url)
        return _BUSINESS_PLATFORM_REPO


def get_microservice_repository():
    global _MICROSERVICE_REPO
    with _REPO_LOCK:
        if _MICROSERVICE_REPO is None:
            _MICROSERVICE_REPO = create_microservice_repository(database_url=_SETTINGS.database_url)
        return _MICROSERVICE_REPO


def get_settings():
    return _SETTINGS


def should_run_background_tasks() -> bool:
    return _SETTINGS.execution_mode == "background"


def get_task_executor():
    from deployment_package_factory.services.deployment_packages.task_executor import (
        PackageTaskExecutor,
        PackageTaskExecutorConfig,
    )

    global _TASK_EXECUTOR
    with _REPO_LOCK:
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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


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


def _operator(request, explicit_operator: str | None) -> str:
    if explicit_operator and explicit_operator.strip():
        return explicit_operator.strip()
    if getattr(request.state, "deployment_package_authenticated", False):
        return "api-token"
    return "anonymous"


def _client_ip(request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else ""


def _audit(
    request,
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


def request_business_namespaces(request, platforms: list[RegisteredBusinessPlatform]) -> list[str]:
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


def request_microservices(request) -> list[dict]:
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
