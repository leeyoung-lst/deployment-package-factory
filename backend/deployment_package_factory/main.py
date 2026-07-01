from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from deployment_package_factory.api._common import (
    get_audit_repository,
    get_business_platform_repository,
    get_microservice_repository,
    get_task_repository,
)
from deployment_package_factory.api.business_platforms import router as business_platforms_router
from deployment_package_factory.api.deployment_packages import router as deployment_packages_router
from deployment_package_factory.api.downloads import router as downloads_router
from deployment_package_factory.api.environment_reset import router as environment_reset_router
from deployment_package_factory.api.microservices import router as microservices_router
from deployment_package_factory.api.settings import router as settings_router
from deployment_package_factory.metrics import render_metrics
from deployment_package_factory.readiness import build_readiness_report
from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.deployment_packages.builder import check_image_export_environment


LOGGER = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(
        title="Deployment Package Factory",
        version="0.1.0",
        description="Standalone service for exporting production deployment packages.",
    )
    # CORS: allow_credentials 仅在明确配置了特定 origin 时启用，
    # 通配符 "*" 与 credentials=True 不兼容（浏览器会拒绝）。
    cors_origins = settings.cors_allowed_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if not settings.api_token:
        LOGGER.warning(
            "DEPLOYMENT_PACKAGE_API_TOKEN is not set — all API endpoints are accessible without authentication. "
            "This is acceptable for local development only; set the token before deploying to production."
        )
    app.include_router(deployment_packages_router)
    app.include_router(downloads_router)
    app.include_router(business_platforms_router)
    app.include_router(environment_reset_router)
    app.include_router(microservices_router)
    app.include_router(settings_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": "deployment-package-factory"}

    @app.get("/health/ready")
    async def ready() -> JSONResponse:
        report = build_readiness_report(
            settings=load_settings(),
            task_repository=get_task_repository,
            audit_repository=get_audit_repository,
            business_platform_repository=get_business_platform_repository,
            microservice_repository=get_microservice_repository,
            image_export_environment=check_image_export_environment,
        )
        return JSONResponse(report, status_code=200 if report["status"] in {"ready", "degraded"} else 503)

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(
            render_metrics(get_task_repository(), get_audit_repository()),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app


app = create_app()
