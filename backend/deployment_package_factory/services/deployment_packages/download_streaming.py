from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class InvalidRangeError(ValueError):
    pass


@dataclass(frozen=True)
class DownloadMetadata:
    filename: str
    size: int
    sha256: str
    etag: str
    last_modified: str

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'attachment; filename="{self.filename}"',
            "Content-Length": str(self.size),
            "ETag": self.etag,
            "Last-Modified": self.last_modified,
            "X-Deployment-Package-Sha256": self.sha256,
        }


@dataclass(frozen=True)
class DownloadRange:
    start: int
    end: int
    total: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    @property
    def content_range(self) -> str:
        return f"bytes {self.start}-{self.end}/{self.total}"


def parse_range_header(value: str, total: int) -> DownloadRange | None:
    if not value:
        return None
    if not value.startswith("bytes=") or "," in value:
        raise InvalidRangeError("Only a single bytes range is supported.")
    start_text, separator, end_text = value[6:].partition("-")
    if separator != "-":
        raise InvalidRangeError("Invalid range header.")
    if start_text == "":
        return _suffix_range(end_text, total)
    try:
        start = int(start_text)
        end = int(end_text) if end_text else total - 1
    except ValueError as exc:
        raise InvalidRangeError("Invalid range header.") from exc
    if start < 0 or end < start or start >= total:
        raise InvalidRangeError("Requested range is not satisfiable.")
    return DownloadRange(start=start, end=min(end, total - 1), total=total)


def should_ignore_range(if_range: str, metadata: DownloadMetadata) -> bool:
    if not if_range:
        return False
    value = if_range.strip()
    return value not in {metadata.etag, metadata.last_modified}


def iter_file_chunks(path: Path, *, start: int = 0, end: int | None = None, chunk_size: int = 1024 * 1024):
    remaining = None if end is None else end - start + 1
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining is None or remaining > 0:
            read_size = chunk_size if remaining is None else min(chunk_size, remaining)
            chunk = handle.read(read_size)
            if not chunk:
                break
            if remaining is not None:
                remaining -= len(chunk)
            yield chunk


def _suffix_range(value: str, total: int) -> DownloadRange:
    try:
        length = int(value)
    except ValueError as exc:
        raise InvalidRangeError("Invalid suffix range.") from exc
    if length <= 0:
        raise InvalidRangeError("Invalid suffix range.")
    start = max(total - length, 0)
    return DownloadRange(start=start, end=total - 1, total=total)
