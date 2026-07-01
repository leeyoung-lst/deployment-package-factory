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
    # SECURITY: Token 通过 URL 查询参数传递时会出现在服务器访问日志、浏览器历史和代理日志中。
    # 仅对下载/校验等需要直接通过 URL 调用的端点开启，其他端点必须使用 Header 传递 Token。
    # 生产环境建议在反向代理层对包含 token 参数的请求 URL 进行脱敏日志记录。
    path = request.url.path.rstrip("/")
    return path.endswith("/download") or path.endswith("/checksum") or path.endswith("/download-script.ps1") or path.endswith("/download-script.sh")
