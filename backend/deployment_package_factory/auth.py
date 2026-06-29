from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, Query, Request, status

from deployment_package_factory.settings import load_settings


async def require_api_token(
    request: Request,
    authorization: str | None = Header(default=None),
    x_deployment_package_token: str | None = Header(default=None),
    deployment_package_token: str | None = Query(default=None),
) -> None:
    expected_token = load_settings().api_token
    if not expected_token:
        return
    query_token = deployment_package_token if _allows_query_token(request) else None
    provided_token = _extract_token(authorization, x_deployment_package_token, query_token)
    if not provided_token or not secrets.compare_digest(provided_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Deployment package API token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.deployment_package_authenticated = True


def _extract_token(authorization: str | None, fallback: str | None, query_token: str | None = None) -> str:
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            return value.strip()
    return (fallback or query_token or "").strip()


def _allows_query_token(request: Request) -> bool:
    path = request.url.path.rstrip("/")
    return path.endswith("/download") or path.endswith("/checksum")
