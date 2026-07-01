"""Deployment package download, checksum, and script API routes.

Split from deployment_packages.py to stay within the 250-line limit.
"""
from __future__ import annotations

from email.utils import formatdate
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from deployment_package_factory.auth import require_api_token
from deployment_package_factory.api._common import _audit
from deployment_package_factory.services.deployment_packages.download_scripts import render_download_script
from deployment_package_factory.services.deployment_packages.download_streaming import (
    DownloadMetadata,
    InvalidRangeError,
    iter_file_chunks,
    parse_range_header,
    should_ignore_range,
)
from deployment_package_factory.services.deployment_packages.models import PackageBuildResult, PackageTask

router = APIRouter(
    prefix="/api/deployment-packages",
    tags=["deployment-packages"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/{package_id}", response_model=PackageBuildResult)
async def get_deployment_package(package_id: str) -> PackageBuildResult:
    task = _find_completed_task(package_id)
    if task is None or task.result is None:
        raise HTTPException(status_code=404, detail="Deployment package task not found")
    return task.result


@router.get("/{package_id}/download")
async def download_deployment_package(
    package_id: str, request: Request,
    range_header: str | None = Header(default=None, alias="Range"),
    if_range: str | None = Header(default=None, alias="If-Range"),
    x_deployment_package_operator: str | None = Header(default=None),
) -> StreamingResponse:
    task, artifact = _completed_artifact(package_id)
    metadata = _download_metadata(task.result, artifact)
    active_range = "" if should_ignore_range(if_range or "", metadata) else (range_header or "")
    try:
        download_range = parse_range_header(active_range, metadata.size)
    except InvalidRangeError as exc:
        raise HTTPException(status_code=416, detail=str(exc), headers={"Content-Range": f"bytes */{metadata.size}"}) from exc
    headers = {**metadata.headers, "Content-Length": str(download_range.length if download_range else metadata.size)}
    if download_range:
        headers["Content-Range"] = download_range.content_range
    audit_metadata = {"taskId": task.task_id, "artifactPath": task.result.artifact_path}
    return StreamingResponse(
        _stream_with_audit(
            iter_file_chunks(artifact, start=download_range.start, end=download_range.end) if download_range else iter_file_chunks(artifact),
            request=request, action="package.download", target_id=task.result.package_id,
            operator=x_deployment_package_operator, metadata=audit_metadata,
        ),
        media_type="application/gzip",
        status_code=206 if download_range else 200,
        headers=headers,
    )


@router.head("/{package_id}/download")
async def head_deployment_package_download(package_id: str) -> Response:
    task, artifact = _completed_artifact(package_id)
    return Response(status_code=200, headers=_download_metadata(task.result, artifact).headers)


@router.get("/{package_id}/checksum")
async def download_deployment_package_checksum(
    package_id: str, request: Request, x_deployment_package_operator: str | None = Header(default=None),
) -> FileResponse:
    task = _find_completed_task(package_id)
    if task is None or task.result is None:
        raise HTTPException(status_code=404, detail="Deployment package task not found")
    checksum = _checksum_path(task.result)
    if not checksum.exists():
        raise HTTPException(status_code=404, detail="Deployment package checksum not found")
    _audit(
        request, action="package.checksum.download", status="completed", target_id=task.result.package_id,
        message="Deployment package checksum downloaded.", operator=x_deployment_package_operator,
        metadata={"taskId": task.task_id, "checksumPath": str(checksum)},
    )
    return FileResponse(
        checksum, media_type="text/plain", filename=checksum.name,
        headers={"X-Deployment-Package-Sha256": task.result.sha256},
    )


@router.get("/{package_id}/download-script.ps1")
async def download_deployment_package_powershell_script(
    package_id: str, request: Request, deployment_package_token: str = Query(default=""),
) -> Response:
    task, artifact = _completed_artifact(package_id)
    metadata = _download_metadata(task.result, artifact)
    content = render_download_script(
        task.result.package_id, task.result.sha256, shell="powershell",
        size=metadata.size, etag=metadata.etag, base_url=_package_base_url(request), token=deployment_package_token,
    )
    return Response(
        content=content, media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{task.result.package_id}-download.ps1"'},
    )


@router.get("/{package_id}/download-script.sh")
async def download_deployment_package_shell_script(
    package_id: str, request: Request, deployment_package_token: str = Query(default=""),
) -> Response:
    task, artifact = _completed_artifact(package_id)
    metadata = _download_metadata(task.result, artifact)
    content = render_download_script(
        task.result.package_id, task.result.sha256, shell="bash",
        size=metadata.size, etag=metadata.etag, base_url=_package_base_url(request), token=deployment_package_token,
    )
    return Response(
        content=content, media_type="text/x-shellscript; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{task.result.package_id}-download.sh"'},
    )


# -- local helpers -----------------------------------------------------------


def _find_completed_task(package_or_task_id: str) -> PackageTask | None:
    from deployment_package_factory.api._common import get_task_repository
    repo = get_task_repository()
    task = repo.get(package_or_task_id)
    if task and task.status == "completed":
        return task
    # Fallback: lookup by result.package_id via SQL (avoids full table scan in Python)
    return repo.get_by_package_id(package_or_task_id)


def _package_base_url(request: Request) -> str:
    return str(request.url_for("deployment_package_options")).rsplit("/options", 1)[0]


def _completed_artifact(package_id: str) -> tuple[PackageTask, Path]:
    task = _find_completed_task(package_id)
    if task is None or task.result is None:
        raise HTTPException(status_code=404, detail="Deployment package task not found")
    artifact = Path(task.result.artifact_path)
    if not artifact.exists():
        raise HTTPException(status_code=404, detail="Deployment package artifact not found")
    return task, artifact


def _download_metadata(result: PackageBuildResult, artifact: Path) -> DownloadMetadata:
    stat = artifact.stat()
    return DownloadMetadata(
        filename=artifact.name, size=stat.st_size, sha256=result.sha256,
        etag=f'"{result.sha256}"', last_modified=formatdate(stat.st_mtime, usegmt=True),
    )


def _checksum_path(result: PackageBuildResult) -> Path:
    if result.checksum_path:
        return Path(result.checksum_path)
    artifact = Path(result.artifact_path)
    return artifact.with_name(f"{artifact.name}.sha256")


def _stream_with_audit(chunks, *, request, action, target_id, operator, metadata=None):
    """Wrap a streaming generator so the audit event fires after the first chunk is sent."""
    audited = False
    for chunk in chunks:
        if not audited:
            _audit(
                request, action=action, status="completed", target_id=target_id,
                message="Deployment package downloaded.", operator=operator, metadata=metadata,
            )
            audited = True
        yield chunk
