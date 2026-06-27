from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True)
class DeploymentPackageSettings:
    data_dir: Path
    task_db_path: Path
    output_dir: Path
    max_concurrent_builds: int
    execution_mode: str
    worker_poll_interval_seconds: int
    running_task_timeout_minutes: int
    retention_days: int
    max_total_gb: int


def load_settings() -> DeploymentPackageSettings:
    data_dir = Path(os.getenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(DEFAULT_DATA_DIR))).expanduser()
    task_db_path = Path(
        os.getenv("DEPLOYMENT_PACKAGE_TASK_DB", str(data_dir / "deployment-package-tasks.sqlite3"))
    ).expanduser()
    output_dir = Path(os.getenv("DEPLOYMENT_PACKAGE_OUTPUT_DIR", str(data_dir / "deployment-packages"))).expanduser()
    return DeploymentPackageSettings(
        data_dir=data_dir,
        task_db_path=task_db_path,
        output_dir=output_dir,
        max_concurrent_builds=_positive_int(os.getenv("DEPLOYMENT_PACKAGE_MAX_CONCURRENT_BUILDS"), default=1),
        execution_mode=_execution_mode(os.getenv("DEPLOYMENT_PACKAGE_EXECUTION_MODE")),
        worker_poll_interval_seconds=_positive_int(os.getenv("DEPLOYMENT_PACKAGE_WORKER_POLL_INTERVAL_SECONDS"), default=3),
        running_task_timeout_minutes=_positive_int(os.getenv("DEPLOYMENT_PACKAGE_RUNNING_TASK_TIMEOUT_MINUTES"), default=120),
        retention_days=_positive_int(os.getenv("DEPLOYMENT_PACKAGE_RETENTION_DAYS"), default=30),
        max_total_gb=_positive_int(os.getenv("DEPLOYMENT_PACKAGE_MAX_TOTAL_GB"), default=500),
    )


def _positive_int(raw: str | None, *, default: int) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)


def _execution_mode(raw: str | None) -> str:
    value = (raw or "background").strip().lower()
    return value if value in {"background", "worker"} else "background"
