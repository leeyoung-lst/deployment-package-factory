from __future__ import annotations

import os
from pathlib import Path


def default_template_dir() -> Path:
    configured = os.getenv("DEPLOYMENT_PACKAGE_TEMPLATE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()

    project_root = Path(__file__).resolve().parents[4]
    candidates = [
        Path.cwd() / "templates",
        project_root / "templates",
        Path("/app/templates"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def default_catalog_dir() -> Path:
    return default_template_dir() / "catalog"


def default_overlay_template_dir() -> Path:
    return default_template_dir() / "overlays"
