from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deployment_package_factory.api.deployment_packages import router as deployment_packages_router


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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": "deployment-package-factory"}

    return app


app = create_app()
