from __future__ import annotations

from collections import defaultdict

from deployment_package_factory.services.deployment_packages.catalog import CatalogError
from deployment_package_factory.services.deployment_packages.models import (
    DeploymentCatalog,
    PackagePreview,
    PackagePreviewRequest,
    ResolvedDependency,
)


def resolve_package_preview(request: PackagePreviewRequest, catalog: DeploymentCatalog) -> PackagePreview:
    database_key = request.database
    if database_key not in catalog.database_options:
        raise CatalogError(f"Unsupported database option {database_key!r}.")

    selected_business = [item.name for item in request.business_services]
    unknown_business = sorted(set(selected_business) - set(catalog.business))
    if unknown_business:
        raise CatalogError(f"Unknown business services: {unknown_business}")

    selected_platform: set[str] = set(catalog.default_platform)
    selected_platform.update(key for key, capability in catalog.platform.items() if capability.required)
    selected_platform.update(request.platform_services)

    required_by: dict[str, set[str]] = defaultdict(set)
    middleware_required_by: dict[str, set[str]] = defaultdict(set)

    for business_key in selected_business:
        business = catalog.business[business_key]
        for platform_key in business.depends_on:
            selected_platform.add(platform_key)
            required_by[platform_key].add(business_key)
        for middleware_key in business.middleware:
            middleware_required_by[middleware_key].add(business_key)

    changed = True
    while changed:
        changed = False
        for platform_key in list(selected_platform):
            capability = catalog.platform.get(platform_key)
            if capability is None:
                raise CatalogError(f"Unknown platform service {platform_key!r}.")
            for dependency in capability.depends_on:
                if dependency not in selected_platform:
                    selected_platform.add(dependency)
                    changed = True
                required_by[dependency].add(platform_key)

    for platform_key in selected_platform:
        capability = catalog.platform[platform_key]
        for middleware_key in capability.middleware:
            middleware_required_by[middleware_key].add(platform_key)

    middleware_keys = set(middleware_required_by)
    if "database" in middleware_keys:
        middleware_keys.remove("database")
        middleware_keys.add(database_key)

    platform_items = [
        _resolved_platform(key, catalog, required_by)
        for key in sorted(selected_platform)
    ]
    business_items = [
        ResolvedDependency(
            key=key,
            name=catalog.business[key].name,
            locked=False,
            requiredBy=[],
            reason="用户选择的业务平台服务",
        )
        for key in selected_business
    ]
    middleware_items = [
        _resolved_middleware(key, catalog, middleware_required_by)
        for key in sorted(middleware_keys)
    ]

    return PackagePreview(
        platformServices=platform_items,
        businessServices=business_items,
        middleware=middleware_items,
        database=catalog.database_options[database_key],
        images=_resolve_images(selected_platform, selected_business, middleware_keys, catalog),
        warnings=[],
    )


def _resolved_platform(
    key: str,
    catalog: DeploymentCatalog,
    required_by: dict[str, set[str]],
) -> ResolvedDependency:
    capability = catalog.platform[key]
    reasons = sorted(required_by.get(key, set()))
    locked = capability.required or bool(reasons)
    return ResolvedDependency(
        key=key,
        name=capability.name,
        locked=locked,
        requiredBy=reasons,
        reason=_reason(capability.name, reasons) if reasons else ("必选基础平台服务" if capability.required else "用户选择的基础平台服务"),
    )


def _resolved_middleware(
    key: str,
    catalog: DeploymentCatalog,
    required_by: dict[str, set[str]],
) -> ResolvedDependency:
    if key in catalog.database_options:
        option = catalog.database_options[key]
        name = option.name
    else:
        name = catalog.middleware[key].name
    reasons = sorted(required_by.get("database" if key in catalog.database_options else key, set()))
    return ResolvedDependency(
        key=key,
        name=name,
        locked=True,
        requiredBy=reasons,
        reason=_reason(name, reasons),
    )


def _reason(name: str, reasons: list[str]) -> str:
    if not reasons:
        return f"{name} 已被所选能力启用"
    return f"{'、'.join(reasons)} 依赖 {name}"


def _resolve_images(
    platform_keys: set[str],
    business_keys: list[str],
    middleware_keys: set[str],
    catalog: DeploymentCatalog,
) -> dict[str, list[str]]:
    platform_images = sorted({image for key in platform_keys for image in catalog.platform[key].images})
    business_images = sorted({image for key in business_keys for image in catalog.business[key].images})
    middleware_images = []
    for key in sorted(middleware_keys):
        if key in catalog.database_options:
            middleware_images.append(catalog.database_options[key].image)
        else:
            middleware_images.append(catalog.middleware[key].image)
    return {
        "platform": platform_images,
        "business": business_images,
        "middleware": sorted(set(middleware_images)),
    }
