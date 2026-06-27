from __future__ import annotations

import tarfile

from deployment_package_factory.services.deployment_packages.builder import build_deployment_package
from deployment_package_factory.services.deployment_packages.models import BusinessSelection, PackageBuildRequest


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
    assert f"{root}/docker-compose/docker-compose.yml" in names
    assert f"{root}/security/SHA256SUMS" in names
