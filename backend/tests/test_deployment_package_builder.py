from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Sequence

import pytest

from deployment_package_factory.services.deployment_packages import builder
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
    checksum = tmp_path / "artifacts" / f"local-ai-prod-package-{result.package_id}.tar.gz.sha256"
    assert artifact.exists()
    assert checksum.exists()
    assert result.sha256
    assert result.checksum_path == str(checksum)
    assert result.artifact_size == artifact.stat().st_size
    assert result.validation_summary["artifactSize"] == artifact.stat().st_size
    assert result.validation_summary["packageIndexFileCount"] > 0
    assert result.validation_summary["imageEntryCount"] > 0
    assert result.validation_summary["imageArchiveCount"] == 0
    assert result.validation_summary["missingImageArchiveCount"] == 0
    assert checksum.read_text(encoding="utf-8") == f"{result.sha256}  {artifact.name}\n"
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
    assert f"{root}/deploy-values.json" in names
    assert f"{root}/package-index.json" in names
    assert f"{root}/README.md" in names
    assert f"{root}/install.sh" in names
    assert f"{root}/install.ps1" in names
    assert f"{root}/verify.sh" in names
    assert f"{root}/verify.ps1" in names
    assert f"{root}/quality-gate.sh" in names
    assert f"{root}/quality-gate.ps1" in names
    assert f"{root}/docs/quality-report.md" in names
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
    quality_gate = (root / "quality-gate.sh").read_text(encoding="utf-8")
    quality_report = (root / "docs" / "quality-report.md").read_text(encoding="utf-8")
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
    assert "verify.sh" in quality_gate
    assert "k8s/dry-run.sh" in quality_gate
    assert "docker-compose/dry-run.sh" in quality_gate
    assert "Deployment Package Quality Report" in quality_report
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
    actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    indexed_files = [item["path"] for section in index["sections"].values() for item in section]
    signed_files = {line.split("  ", 1)[1] for line in sha_sums.splitlines() if line}

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
    assert index["qualityGate"]["version"] == "1.0.0"
    assert index["qualityGate"]["entrypoints"] == ["quality-gate.sh", "quality-gate.ps1"]
    assert "k8s-dry-run" in index["qualityGate"]["checks"]
    assert index["qualityGate"]["report"] == "docs/quality-report.runtime.md"
    assert index["qualityGate"]["template"] == "docs/quality-report.md"
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
    assert any(item["path"] == "quality-gate.sh" and item["executable"] for item in index["sections"]["root"])
    assert any(item["path"] == "quality-gate.ps1" for item in index["sections"]["root"])
    assert any(item["path"] == "deploy-values.json" for item in index["sections"]["root"])
    assert any(item["path"] == "docs/quality-report.md" for item in index["sections"]["docs"])
    assert any(item["path"] == "overlays/mes-lite/values.json" for item in index["sections"]["overlays"])
    assert any(item["path"] == "scripts/load-images.sh" and item["executable"] for item in index["sections"]["scripts"])
    assert "package-index.json" in sha_sums
    assert "quality-gate.sh" in sha_sums
    assert "docs/quality-report.md" in sha_sums
    assert signed_files == actual_files - {"security/SHA256SUMS"}
    assert set(indexed_files) == actual_files - {"package-index.json", "security/SHA256SUMS"}
    assert len(indexed_files) == len(set(indexed_files))


def test_generated_powershell_verifier_rejects_unsigned_package_files(tmp_path) -> None:
    if shutil.which("powershell") is None and shutil.which("pwsh") is None:
        return
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    result = build_deployment_package(
        PackageBuildRequest(projectKey="mes-lite"),
        output_dir=tmp_path,
    )
    root = tmp_path / "work" / result.package_id / f"local-ai-prod-package-{result.package_id}"

    clean = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "verify.ps1")],
        capture_output=True,
        text=True,
    )
    assert clean.returncode == 0, clean.stderr + clean.stdout

    (root / "unexpected.txt").write_text("not signed\n", encoding="utf-8")
    tampered = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "verify.ps1")],
        capture_output=True,
        text=True,
    )

    assert tampered.returncode != 0
    assert "SHA256SUMS file set mismatch" in tampered.stderr + tampered.stdout


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
    deploy_values = json.loads((root / "deploy-values.json").read_text(encoding="utf-8"))
    overlay_sql = root / "overlays" / "mes-lite" / "files" / "init" / "dm" / "010_mes_lite_schema.sql"
    merged_init_sql = root / "init" / "project" / "mes-lite" / "dm" / "010_mes_lite_schema.sql"
    merged_qdrant = root / "init" / "project" / "mes-lite" / "qdrant" / "collections.json"
    init_runner = (root / "init" / "run-init.sh").read_text(encoding="utf-8")

    assert result.manifest["projectKey"] == "mes-lite"
    assert result.manifest["projectProfile"]["overlays"] == ["lite"]
    assert result.manifest["productVersion"] == "2026.06"
    assert result.manifest["imageTag"] == "2026.06-lite"
    assert result.manifest["businessServices"] == ["mes"]
    assert result.manifest["database"] == "dm"
    assert result.manifest["targetProfile"]["registry"] == "harbor.example.com/mes"
    assert result.manifest["targetProfile"]["namespacePrefix"] == "mes-prod"
    assert result.manifest["targetProfile"]["domain"] == "mes.example.com"
    assert deploy_values["schemaVersion"] == "deployment-values/v1"
    assert deploy_values["projectKey"] == "mes-lite"
    assert deploy_values["targetProfile"]["namespacePrefix"] == "mes-prod"
    assert deploy_values["namespaces"]["basePublic"] == "mes-prod-base-public"
    assert deploy_values["namespaces"]["business"]["mes"] == "mes-prod-business-mes"
    assert deploy_values["database"]["key"] == "dm"
    assert deploy_values["validationSummary"]["packageIndexFileCount"] > 0
    assert any(item["key"] == "mes" and item["group"] == "business" for item in deploy_values["services"])
    assert deploy_values["images"]
    assert "harbor.example.com/mes/local-ai-mes-service:2026.06-lite" in deployments
    assert overlay_values["projectKey"] == "mes-lite"
    assert overlay_values["imageTag"] == "2026.06-lite"
    assert overlay_values["overlays"] == ["lite"]
    assert overlay_sql.exists()
    assert merged_init_sql.exists()
    assert merged_qdrant.exists()
    assert "PROJECT_INIT_DIR" in init_runner


def test_standard_eam_project_camunda_assets_are_merged(tmp_path) -> None:
    result = build_deployment_package(
        PackageBuildRequest(projectKey="standard-eam"),
        output_dir=tmp_path,
    )
    root = tmp_path / "work" / result.package_id / f"local-ai-prod-package-{result.package_id}"
    model = root / "init" / "project" / "standard-eam" / "camunda" / "eam-repair.bpmn"
    bootstrap = (root / "init" / "camunda" / "bootstrap-admin.sh").read_text(encoding="utf-8")

    assert model.exists()
    assert "eam_repair" in model.read_text(encoding="utf-8")
    assert "deployment/create" in bootstrap
    assert "deploy_process_model" in bootstrap


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
    assert result.artifact_size > 0
    assert result.validation_summary["imageEntryCount"] == len(lock["images"])
    assert result.validation_summary["imageArchiveCount"] == len(lock["archives"])
    assert result.validation_summary["missingImageArchiveCount"] == 0
    assert all(item["targetRef"].startswith("harbor.example.com/prod/") for item in lock["images"])
    assert all((root / "images" / "archives" / item["file"]).exists() for item in lock["archives"])


def test_image_archive_uses_source_registry_separately_from_target_registry(tmp_path) -> None:
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
            platformServices=["iam", "gateway-frontend"],
            businessServices=[],
            database="postgres",
            imageMode="image-archive",
            targetProfile=TargetProfile(
                sourceRegistry="harbor.internal/local-ai",
                registry="harbor.prod/local-ai",
            ),
        ),
        output_dir=tmp_path,
        docker_runner=fake_docker_runner,
    )

    root = tmp_path / "work" / result.package_id / f"local-ai-prod-package-{result.package_id}"
    lock = json.loads((root / "security" / "image-digest-lock.json").read_text(encoding="utf-8"))

    assert any(command == ["docker", "pull", "harbor.internal/local-ai/postgres:16"] for command in commands)
    assert all(item["sourceRef"].startswith("harbor.internal/local-ai/") for item in lock["images"])
    assert all(item["targetRef"].startswith("harbor.prod/local-ai/") for item in lock["images"])
    assert any(item["catalogRef"] == "postgres:16" for item in lock["images"])


def test_image_entries_use_runtime_kubernetes_images_for_source_env(monkeypatch) -> None:
    monkeypatch.setattr(builder, "_source_env_namespaces", lambda source_env: ["local-ai"] if source_env == "test" else [])
    monkeypatch.setattr(
        builder,
        "_list_runtime_images",
        lambda namespaces: [
            builder.RuntimeSourceImage(
                source_ref="192.168.10.210/local-ai/local-ai-eam-service:k8s",
                image_id="192.168.10.210/local-ai/local-ai-eam-service@sha256:eam",
                namespace="local-ai",
                pod="eam-service-1",
                container="eam-service",
            ),
            builder.RuntimeSourceImage(
                source_ref="192.168.10.210/local-ai/local-ai-sub-app-eam:k8s",
                image_id="192.168.10.210/local-ai/local-ai-sub-app-eam@sha256:subapp",
                namespace="local-ai",
                pod="sub-app-eam-1",
                container="sub-app-eam",
            ),
            builder.RuntimeSourceImage(
                source_ref="postgres:16-alpine",
                image_id="sha256:postgres",
                namespace="local-ai",
                pod="postgres-1",
                container="postgres",
            ),
        ],
    )

    result = build_deployment_package(
        PackageBuildRequest(
            sourceEnv="test",
            deployModes=["k8s"],
            businessServices=[BusinessSelection(name="eam", profile="4x60")],
            database="postgres",
            targetProfile=TargetProfile(registry="harbor.prod/local-ai"),
        )
    )

    by_catalog = {item["catalogRef"]: item for item in result.manifest["imageEntries"]}

    assert by_catalog["local-ai-eam-service:prod"]["sourceRef"] == "192.168.10.210/local-ai/local-ai-eam-service:k8s"
    assert by_catalog["local-ai-eam-service:prod"]["sourceExportRef"] == "192.168.10.210/local-ai/local-ai-eam-service@sha256:eam"
    assert by_catalog["sub-app-eam:prod"]["sourceRef"] == "192.168.10.210/local-ai/local-ai-sub-app-eam:k8s"
    assert by_catalog["postgres:16"]["sourceRef"] == "postgres:16-alpine"
    assert by_catalog["local-ai-eam-service:prod"]["targetRef"] == "harbor.prod/local-ai/local-ai-eam-service:prod"
    assert by_catalog["local-ai-eam-service:prod"]["sourceResolvedFrom"] == "kubernetes"


def test_list_runtime_images_includes_pending_pod_spec_images(monkeypatch, tmp_path) -> None:
    token_path = tmp_path / "token"
    token_path.write_text("token", encoding="utf-8")
    monkeypatch.setenv("KUBERNETES_SERVICEACCOUNT_TOKEN_PATH", str(token_path))
    monkeypatch.setattr(
        builder,
        "read_kubernetes_pods",
        lambda namespace, token: {
            "items": [
                {
                    "metadata": {"name": "iam-service-pending"},
                    "status": {"phase": "Pending", "containerStatuses": []},
                    "spec": {"containers": [{"name": "iam", "image": "192.168.10.210/local-ai/local-ai-iam-service:abc123"}]},
                }
            ]
        },
    )

    images = builder._list_runtime_images(["local-ai"])

    assert images == [
        builder.RuntimeSourceImage(
            source_ref="192.168.10.210/local-ai/local-ai-iam-service:abc123",
            image_id="",
            namespace="local-ai",
            pod="iam-service-pending",
            container="iam",
        )
    ]


def test_image_entries_mark_missing_runtime_sources_when_cluster_images_are_available(monkeypatch) -> None:
    monkeypatch.setattr(builder, "_source_env_namespaces", lambda source_env: ["local-ai"] if source_env == "test" else [])
    monkeypatch.setattr(
        builder,
        "_list_runtime_images",
        lambda namespaces: [
            builder.RuntimeSourceImage(
                source_ref="192.168.10.210/local-ai/local-ai-eam-service:k8s",
                image_id="192.168.10.210/local-ai/local-ai-eam-service@sha256:eam",
                namespace="local-ai",
                pod="eam-service-1",
                container="eam-service",
            )
        ],
    )

    result = build_deployment_package(
        PackageBuildRequest(
            sourceEnv="test",
            deployModes=["k8s"],
            businessServices=[BusinessSelection(name="eam", profile="4x60")],
            database="postgres",
            targetProfile=TargetProfile(registry="harbor.prod/local-ai"),
        )
    )

    by_catalog = {item["catalogRef"]: item for item in result.manifest["imageEntries"]}

    assert by_catalog["local-ai-eam-service:prod"]["sourceResolvedFrom"] == "kubernetes"
    assert by_catalog["local-ai-iam-service:prod"]["sourceMissing"] is True
    assert by_catalog["local-ai-iam-service:prod"]["sourceResolvedFrom"] == "missing"
    assert "未在来源环境 test" in by_catalog["local-ai-iam-service:prod"]["sourceMessage"]


def test_check_image_export_environment_reports_available_docker(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(builder.shutil, "which", lambda command: None)

    def fake_run(command, check, capture_output, text):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="Docker version 26.1.0\n", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    result = builder.check_image_export_environment()

    assert result.available is True
    assert result.export_tool == "docker"
    assert result.docker_version == "Docker version 26.1.0"
    assert result.message == "Docker CLI and daemon are available for image archive export."
    assert calls == [["docker", "--version"], ["docker", "info"]]


def test_check_image_export_environment_prefers_skopeo(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(builder.shutil, "which", lambda command: "/usr/bin/skopeo" if command == "skopeo" else None)

    def fake_run(command, check, capture_output, text):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="skopeo version 1.14.0\n", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    result = builder.check_image_export_environment()

    assert result.available is True
    assert result.export_tool == "skopeo"
    assert result.tool_version == "skopeo version 1.14.0"
    assert result.docker_version == ""
    assert calls == [["skopeo", "--version"]]


def test_check_image_export_environment_reports_missing_docker(monkeypatch) -> None:
    monkeypatch.setattr(builder.shutil, "which", lambda command: None)

    def fake_run(command, check, capture_output, text):
        raise FileNotFoundError()

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    result = builder.check_image_export_environment()

    assert result.available is False
    assert result.export_tool == ""
    assert result.docker_version == ""
    assert "No image export tool is available" in result.message


def test_build_deployment_package_exports_image_archives_with_skopeo(tmp_path, monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(builder.shutil, "which", lambda command: "/usr/bin/skopeo" if command == "skopeo" else None)

    def fake_run(command, check, capture_output, text):
        commands.append(list(command))
        archive = next((part for part in command if part.startswith("docker-archive:")), "")
        if archive:
            archive_path = Path(archive.removeprefix("docker-archive:").rsplit(".tar:", 1)[0] + ".tar")
            archive_path.write_bytes(b"archive")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

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
    )
    root = tmp_path / "work" / result.package_id / f"local-ai-prod-package-{result.package_id}"
    lock = json.loads((root / "security" / "image-digest-lock.json").read_text(encoding="utf-8"))

    assert commands
    copy_commands = [command for command in commands if command[:2] == ["skopeo", "copy"]]
    inspect_commands = [command for command in commands if command[:2] == ["skopeo", "inspect"]]
    assert copy_commands
    assert inspect_commands
    assert lock["archives"]
    assert all((root / "images" / "archives" / item["file"]).exists() for item in lock["archives"])


def test_image_archive_uses_insecure_source_registry_with_skopeo(tmp_path, monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(builder.shutil, "which", lambda command: "/usr/bin/skopeo" if command == "skopeo" else None)

    def fake_run(command, check, capture_output, text):
        commands.append(list(command))
        archive = next((part for part in command if part.startswith("docker-archive:")), "")
        if archive:
            archive_path = Path(archive.removeprefix("docker-archive:").rsplit(".tar:", 1)[0] + ".tar")
            archive_path.write_bytes(b"archive")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    result = build_deployment_package(
        PackageBuildRequest(
            sourceEnv="test",
            deployModes=["k8s"],
            platformServices=["iam", "gateway-frontend"],
            businessServices=[],
            database="postgres",
            imageMode="image-archive",
            targetProfile=TargetProfile(
                sourceRegistry="192.168.10.210/local-ai",
                sourceRegistryInsecure=True,
                registry="harbor.example.com/prod",
            ),
        ),
        output_dir=tmp_path,
    )
    root = tmp_path / "work" / result.package_id / f"local-ai-prod-package-{result.package_id}"
    lock = json.loads((root / "security" / "image-digest-lock.json").read_text(encoding="utf-8"))

    assert commands
    copy_commands = [command for command in commands if command[:2] == ["skopeo", "copy"]]
    inspect_commands = [command for command in commands if command[:2] == ["skopeo", "inspect"]]
    assert copy_commands
    assert inspect_commands
    assert all("--src-tls-verify=false" in command for command in copy_commands)
    assert all("--tls-verify=false" in command for command in inspect_commands)
    assert all(item["sourceRegistryInsecure"] is True for item in lock["images"])


def test_image_archive_auto_uses_insecure_for_private_ip_registry_with_skopeo(tmp_path, monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(builder.shutil, "which", lambda command: "/usr/bin/skopeo" if command == "skopeo" else None)

    def fake_run(command, check, capture_output, text):
        commands.append(list(command))
        archive = next((part for part in command if part.startswith("docker-archive:")), "")
        if archive:
            archive_path = Path(archive.removeprefix("docker-archive:").rsplit(".tar:", 1)[0] + ".tar")
            archive_path.write_bytes(b"archive")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    result = build_deployment_package(
        PackageBuildRequest(
            sourceEnv="test",
            deployModes=["k8s"],
            platformServices=["iam"],
            businessServices=[],
            database="postgres",
            imageMode="image-archive",
            targetProfile=TargetProfile(
                sourceRegistry="192.168.10.210/local-ai",
                registry="harbor.example.com/prod",
            ),
        ),
        output_dir=tmp_path,
    )
    root = tmp_path / "work" / result.package_id / f"local-ai-prod-package-{result.package_id}"
    lock = json.loads((root / "security" / "image-digest-lock.json").read_text(encoding="utf-8"))
    private_registry_items = [item for item in lock["images"] if item["sourceRef"].startswith("192.168.10.210/")]
    copy_commands = [command for command in commands if command[:2] == ["skopeo", "copy"]]
    inspect_commands = [command for command in commands if command[:2] == ["skopeo", "inspect"]]

    assert private_registry_items
    assert all(item["sourceRegistryInsecure"] is True for item in private_registry_items)
    assert all("--src-tls-verify=false" in command for command in copy_commands if "192.168.10.210/" in " ".join(command))
    assert all("--tls-verify=false" in command for command in inspect_commands if "192.168.10.210/" in " ".join(command))


def test_source_registry_insecure_does_not_mark_docker_hub_images() -> None:
    assert builder._source_registry_insecure("redis:7.4-alpine") is False
    assert builder._source_registry_insecure("qdrant/qdrant:v1.18.0") is False
    assert builder._source_registry_insecure("registry-1.docker.io/library/redis:7.4-alpine") is False
    assert builder._source_registry_insecure("192.168.10.210/local-ai/local-ai-backend:k8s") is True


def test_image_archive_uses_source_registry_authfile_with_skopeo(tmp_path, monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setenv("DEPLOYMENT_PACKAGE_SOURCE_REGISTRY_USERNAME", "robot")
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_SOURCE_REGISTRY_PASSWORD", "secret")
    monkeypatch.setattr(builder.shutil, "which", lambda command: "/usr/bin/skopeo" if command == "skopeo" else None)

    def fake_run(command, check, capture_output, text):
        commands.append(list(command))
        auth_arg = "--src-authfile" if "--src-authfile" in command else "--authfile"
        authfile = Path(command[command.index(auth_arg) + 1])
        auth = json.loads(authfile.read_text(encoding="utf-8"))
        assert "192.168.10.210" in auth["auths"]
        assert "secret" not in " ".join(command)
        archive = next((part for part in command if part.startswith("docker-archive:")), "")
        if archive:
            archive_path = Path(archive.removeprefix("docker-archive:").rsplit(".tar:", 1)[0] + ".tar")
            archive_path.write_bytes(b"archive")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    build_deployment_package(
        PackageBuildRequest(
            sourceEnv="test",
            deployModes=["k8s"],
            platformServices=["iam", "gateway-frontend"],
            businessServices=[],
            database="postgres",
            imageMode="image-archive",
            targetProfile=TargetProfile(
                sourceRegistry="192.168.10.210/local-ai",
                sourceRegistryInsecure=True,
                registry="harbor.example.com/prod",
            ),
        ),
        output_dir=tmp_path,
    )

    assert commands
    copy_commands = [command for command in commands if command[:2] == ["skopeo", "copy"]]
    inspect_commands = [command for command in commands if command[:2] == ["skopeo", "inspect"]]
    assert copy_commands
    assert inspect_commands
    assert all("--src-authfile" in command for command in copy_commands)
    assert all("--authfile" in command for command in inspect_commands)


def test_image_archive_preflights_all_source_images_before_export(tmp_path, monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(builder.shutil, "which", lambda command: "/usr/bin/skopeo" if command == "skopeo" else None)

    def fake_run(command, check, capture_output, text):
        commands.append(list(command))
        if command[:2] == ["skopeo", "inspect"]:
            image = command[-1].removeprefix("docker://")
            if image.endswith("postgres:16") or image.endswith("redis:7"):
                raise subprocess.CalledProcessError(1, command, stderr=f"missing {image}")
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    with pytest.raises(builder.PackageBuildError) as exc:
        build_deployment_package(
            PackageBuildRequest(
                sourceEnv="test",
                deployModes=["k8s"],
                platformServices=["iam", "gateway-frontend"],
                businessServices=[],
                database="postgres",
                imageMode="image-archive",
                targetProfile=TargetProfile(
                    sourceRegistry="192.168.10.210/local-ai",
                    sourceRegistryInsecure=True,
                    registry="harbor.example.com/prod",
                ),
            ),
            output_dir=tmp_path,
        )

    assert "Source image preflight failed" in str(exc.value)
    assert "postgres:16" in str(exc.value)
    assert "redis:7" in str(exc.value)
    assert all(command[:2] == ["skopeo", "inspect"] for command in commands)
