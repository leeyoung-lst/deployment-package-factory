from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from deployment_package_factory.api.deployment_packages import get_audit_repository, get_task_repository, router as deployment_packages_router
from deployment_package_factory.api.microservices import router as microservices_router
from deployment_package_factory.metrics import render_metrics


def create_app() -> FastAPI:
    app = FastAPI(
        title="Deployment Package Factory",
        version="0.1.0",
        description="Standalone service for exporting production deployment packages.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(deployment_packages_router)
    app.include_router(microservices_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": "deployment-package-factory"}

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(
            render_metrics(get_task_repository(), get_audit_repository()),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app


app = create_app()
