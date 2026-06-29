from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class TemplateFile:
    path: PurePosixPath
    content: str
    executable: bool = False
