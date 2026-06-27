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

    root = f"local-ai-prod-package-{result.package_id}"
    assert f"{root}/manifest.json" in names
    assert f"{root}/README.md" in names
    assert f"{root}/k8s/namespaces.yaml" in names
    assert f"{root}/k8s/configmaps.yaml" in names
    assert f"{root}/k8s/secrets.template.yaml" in names
    assert f"{root}/k8s/pvcs.yaml" in names
    assert f"{root}/k8s/deployments.yaml" in names
    assert f"{root}/k8s/services.yaml" in names
    assert f"{root}/k8s/ingress.yaml" in names
    assert f"{root}/k8s/jobs/init-db.yaml" in names
    assert f"{root}/k8s/uninstall.sh" in names
    assert f"{root}/docker-compose/docker-compose.yml" in names
    assert f"{root}/docker-compose/install.sh" in names
    assert f"{root}/docker-compose/uninstall.sh" in names
    assert f"{root}/images/images.txt" in names
    assert f"{root}/scripts/pull-images.sh" in names
    assert f"{root}/scripts/save-images.sh" in names
    assert f"{root}/scripts/load-images.sh" in names
    assert f"{root}/images/archives/.gitkeep" in names
    assert f"{root}/security/image-digest-lock.json" in names
    assert f"{root}/security/SHA256SUMS" in names


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
    assert "echo init dm schema" in init_job
    assert "business-mes:" in compose
    assert "dm:" in compose
    assert "postgres:" not in compose


def test_project_defaults_drive_build_target_profile(tmp_path) -> None:
    result = build_deployment_package(
        PackageBuildRequest(projectKey="mes-lite"),
        output_dir=tmp_path,
    )

    assert result.manifest["projectKey"] == "mes-lite"
    assert result.manifest["productVersion"] == "2026.06"
    assert result.manifest["businessServices"] == ["mes"]
    assert result.manifest["database"] == "dm"
    assert result.manifest["targetProfile"]["registry"] == "harbor.example.com/mes"
    assert result.manifest["targetProfile"]["namespacePrefix"] == "mes-prod"
    assert result.manifest["targetProfile"]["domain"] == "mes.example.com"


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
