from __future__ import annotations

import os
import shutil
from pathlib import Path

from deployment_package_factory.services.microservices.scaffold import (
    MicroserviceScaffoldResult,
    find_scaffold_artifact,
    find_scaffold_project_root,
)


def finalize_scaffold_artifacts(result: MicroserviceScaffoldResult, output_dir: Path) -> MicroserviceScaffoldResult:
    if _git_project_ready(result.delivery):
        cleanup_scaffold_artifacts(result.project_id, output_dir)
        result.clone_command = f"git clone {result.git_repository_url}"
    result.artifact_available = scaffold_artifact_available(result.project_id, output_dir)
    return result


def finalize_registered_artifacts(row: dict, delivery: dict[str, object], output_dir: Path) -> dict[str, object]:
    if _git_project_ready(delivery):
        cleanup_scaffold_artifacts(str(row["projectId"]), output_dir)
        return {
            "artifactAvailable": scaffold_artifact_available(str(row["projectId"]), output_dir),
            "cloneCommand": f"git clone {row['gitRepositoryUrl']}",
        }
    return {"artifactAvailable": scaffold_artifact_available(str(row["projectId"]), output_dir)}


def cleanup_scaffold_artifacts(project_id: str, output_dir: Path) -> None:
    root = output_dir.resolve()
    project_root = find_scaffold_project_root(project_id, output_dir=output_dir)
    artifact = find_scaffold_artifact(project_id, output_dir=output_dir)
    if project_root and _inside(project_root, root):
        shutil.rmtree(project_root, onexc=_clear_readonly)
    if artifact and _inside(artifact, root) and artifact.exists():
        artifact.unlink()


def scaffold_artifact_available(project_id: str, output_dir: Path) -> bool:
    artifact = find_scaffold_artifact(project_id, output_dir=output_dir)
    return bool(artifact and artifact.is_file())


def _git_project_ready(delivery: dict[str, object]) -> bool:
    steps = delivery.get("steps") if isinstance(delivery, dict) else None
    return any(step.get("name") == "git-project" and step.get("status") == "ready" for step in steps or [] if isinstance(step, dict))


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return False
    return True


def _clear_readonly(function, path, _excinfo):
    os.chmod(path, 0o700)
    function(path)
