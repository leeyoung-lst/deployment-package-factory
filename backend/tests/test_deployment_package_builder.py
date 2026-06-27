from __future__ import annotations

import json
import tarfile
from pathlib import Path
from typing import Sequence

from deployment_package_factory.services.deployment_packages.builder import build_deployment_package
from deployment_package_factory.services.deployment_packages.models import BusinessSelection, PackageBuildRequest, TargetProfile


def test_build_deployment_package_creates_mvp_archive(tmp_path) -> None:
    result = build_deployment_package(
        PackageBuildRequest(
            sourceEnv="test",
            deployModes=["k8s", "docker-compose"],
            businessServices=[BusinessSelection(name="eam", profile="4x60")],
            database="postgres",
        ),
        output_dir=tmp_path,
    )

    artifact = tmp_path / "artifacts" / f"local-ai-prod-package-{result.package_id}.tar.gz"
    assert artifact.exists()
    assert result.sha256
    assert result.manifest["businessServices"] == ["eam"]
    assert result.manifest["database"] == "postgres"

    with tarfile.open(artifact, "r:gz") as tar:
        names = set(tar.getnames())
        script_modes = {
            item.name: item.mode
            for item in tar.getmembers()
            if item.isfile() and item.name.endswith(".sh")
        }

    root = f"local-ai-prod-package-{result.package_id}"
    assert f"{root}/manifest.json" in names
    assert f"{root}/package-index.json" in names
    assert f"{root}/README.md" in names
    assert f"{root}/install.sh" in names
    assert f"{root}/install.ps1" in names
    assert f"{root}/verify.sh" in names
    assert f"{root}/verify.ps1" in names
    assert f"{root}/k8s/namespaces.yaml" in names
    assert f"{root}/k8s/configmaps.yaml" in names
    assert f"{root}/k8s/secrets.template.yaml" in names
    assert f"{root}/k8s/pvcs.yaml" in names
    assert f"{root}/k8s/deployments.yaml" in names
    assert f"{root}/k8s/services.yaml" in names
    assert f"{root}/k8s/ingress.yaml" in names
    assert f"{root}/k8s/jobs/init-db.yaml" in names
    assert f"{root}/k8s/install.sh" in names
    assert f"{root}/k8s/uninstall.sh" in names
    assert f"{root}/k8s/dry-run.sh" in names
    assert f"{root}/docker-compose/docker-compose.yml" in names
    assert f"{root}/docker-compose/install.sh" in names
    assert f"{root}/docker-compose/uninstall.sh" in names
    assert f"{root}/docker-compose/dry-run.sh" in names
    assert f"{root}/init/run-init.sh" in names
    assert f"{root}/init/README.md" in names
    assert f"{root}/init/postgres/001_schema.sql" in names
    assert f"{root}/init/minio/create-buckets.sh" in names
    assert f"{root}/init/camunda/bootstrap-admin.sh" in names
    assert f"{root}/images/images.txt" in names
    assert f"{root}/scripts/check-prerequisites.sh" in names
    assert f"{root}/scripts/secret-check.sh" in names
    assert f"{root}/scripts/health-check.sh" in names
    assert f"{root}/scripts/pull-images.sh" in names
    assert f"{root}/scripts/save-images.sh" in names
    assert f"{root}/scripts/load-images.sh" in names
    assert f"{root}/images/archives/.gitkeep" in names
    assert f"{root}/security/image-digest-lock.json" in names
    assert f"{root}/security/SHA256SUMS" in names
    assert script_modes
    assert all(mode & 0o111 for mode in script_modes.values())


def test_build_deployment_package_includes_validation_scripts(tmp_path) -> None:
    result = build_deployment_package(
        PackageBuildRequest(
            sourceEnv="test",
            deployModes=["k8s", "docker-compose"],
            businessServices=[BusinessSelection(name="eam", profile="4x60")],
            database="postgres",
        ),
        output_dir=tmp_path,
    )

    root = tmp_path / "work" / result.package_id / f"local-ai-prod-package-{result.package_id}"
    k8s_install = (root / "k8s" / "install.sh").read_text(encoding="utf-8")
    k8s_dry_run = (root / "k8s" / "dry-run.sh").read_text(encoding="utf-8")
    compose_install = (root / "docker-compose" / "install.sh").read_text(encoding="utf-8")
    compose_dry_run = (root / "docker-compose" / "dry-run.sh").read_text(encoding="utf-8")
    root_install = (root / "install.sh").read_text(encoding="utf-8")
    root_install_ps1 = (root / "install.ps1").read_text(encoding="utf-8")
    secret_check = (root / "scripts" / "secret-check.sh").read_text(encoding="utf-8")
    prereq_check = (root / "scripts" / "check-prerequisites.sh").read_text(encoding="utf-8")
    health_check = (root / "scripts" / "health-check.sh").read_text(encoding="utf-8")
    init_runner = (root / "init" / "run-init.sh").read_text(encoding="utf-8")

    assert "scripts/secret-check.sh" in k8s_install
    assert "scripts/secret-check.sh" in compose_install
    assert "init/run-init.sh" in compose_install
    assert "SECRETS_FILE" in k8s_install
    assert "kubectl apply --dry-run=client" in k8s_dry_run
    assert "docker compose --env-file" in compose_dry_run
    assert "docker-compose.yml\" config" in compose_dry_run
    assert "package-index.json" in root_install
    assert "--skip-verify" in root_install
    assert "--skip-dry-run" in root_install
    assert "--skip-health-check" in root_install
    assert "--yes" in root_install
    assert "k8s/dry-run.sh" in root_install
    assert "docker-compose/dry-run.sh" in root_install
    assert "scripts/health-check.sh" in root_install
    assert "verify.sh" in root_install
    assert "ValidateSet('k8s', 'docker-compose')" in root_install_ps1
    assert "[switch]$SkipVerify" in root_install_ps1
    assert "__REPLACE_WITH_" in secret_check
    assert "Secret placeholders remain" in secret_check
    assert "require_command kubectl" in prereq_check
    assert "docker compose version" in prereq_check
    assert "kubectl get pods" in health_check
    assert "docker compose" in health_check
    assert "run_sql \"postgres\"" in init_runner


def test_build_deployment_package_writes_package_index(tmp_path) -> None:
    result = build_deployment_package(
        PackageBuildRequest(projectKey="mes-lite"),
        output_dir=tmp_path,
    )

    root = tmp_path / "work" / result.package_id / f"local-ai-prod-package-{result.package_id}"
    index = json.loads((root / "package-index.json").read_text(encoding="utf-8"))
    sha_sums = (root / "security" / "SHA256SUMS").read_text(encoding="utf-8")

    assert index["schemaVersion"] == "deployment-package-index/v1"
    assert index["packageId"] == result.package_id
    assert index["projectKey"] == "mes-lite"
    assert index["summary"]["fileCount"] > 0
    assert index["installer"]["version"] == "1.2.0"
    assert index["installer"]["entrypoints"] == ["install.sh", "install.ps1"]
    assert index["installer"]["supportedModes"] == ["k8s", "docker-compose"]
    assert "--skip-verify" in index["installer"]["options"]
    assert "--skip-dry-run" in index["installer"]["options"]
    assert index["verifier"]["version"] == "1.0.0"
    assert index["verifier"]["entrypoints"] == ["verify.sh", "verify.ps1"]
    assert "sha256sums" in index["verifier"]["checks"]
    assert index["sections"]["k8s"]
    assert index["sections"]["dockerCompose"]
    assert index["sections"]["init"]
    assert index["sections"]["overlays"]
    assert index["sections"]["images"]
    assert index["sections"]["scripts"]
    assert index["sections"]["security"]
    assert any(item["path"] == "install.sh" and item["executable"] for item in index["sections"]["root"])
    assert any(item["path"] == "install.ps1" for item in index["sections"]["root"])
    assert any(item["path"] == "verify.sh" and item["executable"] for item in index["sections"]["root"])
    assert any(item["path"] == "verify.ps1" for item in index["sections"]["root"])
    assert any(item["path"] == "overlays/mes-lite/values.json" for item in index["sections"]["overlays"])
    assert any(item["path"] == "scripts/load-images.sh" and item["executable"] for item in index["sections"]["scripts"])
    assert "package-index.json" in sha_sums


def test_rendered_k8s_and_compose_include_business_middleware_and_registry(tmp_path) -> None:
    result = build_deployment_package(
        PackageBuildRequest(
            sourceEnv="test",
            deployModes=["k8s", "docker-compose"],
            businessServices=[BusinessSelection(name="mes", profile="4x3")],
            database="dm",
            targetProfile=TargetProfile(
                registry="harbor.example.com/prod",
                namespacePrefix="prod",
                domain="mes.example.com",
                storageClass="fast-ssd",
            ),
        ),
        output_dir=tmp_path,
    )

    root = tmp_path / "work" / result.package_id / f"local-ai-prod-package-{result.package_id}"
    namespaces = (root / "k8s" / "namespaces.yaml").read_text(encoding="utf-8")
    deployments = (root / "k8s" / "deployments.yaml").read_text(encoding="utf-8")
    services = (root / "k8s" / "services.yaml").read_text(encoding="utf-8")
    pvcs = (root / "k8s" / "pvcs.yaml").read_text(encoding="utf-8")
    ingress = (root / "k8s" / "ingress.yaml").read_text(encoding="utf-8")
    init_job = (root / "k8s" / "jobs" / "init-db.yaml").read_text(encoding="utf-8")
    compose = (root / "docker-compose" / "docker-compose.yml").read_text(encoding="utf-8")

    assert "name: prod-base-public" in namespaces
    assert "name: prod-business-mes" in namespaces
    assert "name: prod-middleware" in namespaces
    assert "harbor.example.com/prod/local-ai-mes-service:prod" in deployments
    assert "harbor.example.com/prod/dm8:latest" in deployments
    assert "postgres:16" not in deployments
    assert "storageClassName: fast-ssd" in pvcs
    assert "host: mes.example.com" in ingress
    assert "name: local-ai-mes-service" in services
    assert "name: init-scripts" in init_job
    assert "echo init dm schema and middleware scripts" in init_job
    assert "business-mes:" in compose
    assert "dm:" in compose
    assert "postgres:" not in compose


def test_project_defaults_drive_build_target_profile(tmp_path) -> None:
    result = build_deployment_package(
        PackageBuildRequest(projectKey="mes-lite"),
        output_dir=tmp_path,
    )
    root = tmp_path / "work" / result.package_id / f"local-ai-prod-package-{result.package_id}"
    deployments = (root / "k8s" / "deployments.yaml").read_text(encoding="utf-8")
    overlay_values = json.loads((root / "overlays" / "mes-lite" / "values.json").read_text(encoding="utf-8"))
    overlay_sql = root / "overlays" / "mes-lite" / "files" / "init" / "dm" / "010_mes_lite_schema.sql"

    assert result.manifest["projectKey"] == "mes-lite"
    assert result.manifest["projectProfile"]["overlays"] == ["lite"]
    assert result.manifest["productVersion"] == "2026.06"
    assert result.manifest["imageTag"] == "2026.06-lite"
    assert result.manifest["businessServices"] == ["mes"]
    assert result.manifest["database"] == "dm"
    assert result.manifest["targetProfile"]["registry"] == "harbor.example.com/mes"
    assert result.manifest["targetProfile"]["namespacePrefix"] == "mes-prod"
    assert result.manifest["targetProfile"]["domain"] == "mes.example.com"
    assert "harbor.example.com/mes/local-ai-mes-service:2026.06-lite" in deployments
    assert overlay_values["projectKey"] == "mes-lite"
    assert overlay_values["imageTag"] == "2026.06-lite"
    assert overlay_values["overlays"] == ["lite"]
    assert overlay_sql.exists()


def test_build_deployment_package_exports_image_archives_with_runner(tmp_path) -> None:
    commands: list[list[str]] = []

    def fake_docker_runner(command: Sequence[str]) -> None:
        commands.append(list(command))
        if command[:2] == ["docker", "save"]:
            archive = Path(command[3])
            archive.write_bytes(f"archive for {command[4]}".encode("utf-8"))

    result = build_deployment_package(
        PackageBuildRequest(
            sourceEnv="test",
            deployModes=["k8s"],
            businessServices=[BusinessSelection(name="mes", profile="4x3")],
            database="postgres",
            imageMode="image-archive",
            targetProfile=TargetProfile(registry="harbor.example.com/prod"),
        ),
        output_dir=tmp_path,
        docker_runner=fake_docker_runner,
    )

    root = tmp_path / "work" / result.package_id / f"local-ai-prod-package-{result.package_id}"
    lock = json.loads((root / "security" / "image-digest-lock.json").read_text(encoding="utf-8"))

    assert commands
    assert any(command[:2] == ["docker", "pull"] for command in commands)
    assert any(command[:2] == ["docker", "save"] for command in commands)
    assert lock["archives"]
    assert all(item["targetRef"].startswith("harbor.example.com/prod/") for item in lock["images"])
    assert all((root / "images" / "archives" / item["file"]).exists() for item in lock["archives"])
