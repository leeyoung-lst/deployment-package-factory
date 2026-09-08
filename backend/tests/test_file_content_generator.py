"""测试 file_content_generator 模块"""

import json
from pathlib import Path
from datetime import datetime, timezone

import pytest

from deployment_package_factory.services.deployment_packages.file_content_generator import (
    generate_readme,
    generate_images_txt,
    generate_pull_images_script,
    generate_save_images_script,
    generate_load_images_script,
    generate_validation_summary,
    generate_package_index,
    generate_file_index_entry,
    extract_section,
    extract_section_by_prefix,
)


class TestGenerateReadme:
    def test_basic_readme(self):
        manifest = {
            "packageId": "pkg-20260908-abc123",
            "sourceEnv": "dev",
            "targetEnv": "prod",
            "deployModes": ["k8s", "docker-compose"],
            "database": "postgresql",
        }
        result = generate_readme(manifest)
        assert "pkg-20260908-abc123" in result
        assert "dev" in result
        assert "prod" in result
        assert "k8s, docker-compose" in result
        assert "postgresql" in result
        assert "quality-gate.sh" in result

    def test_readme_with_empty_deploy_modes(self):
        manifest = {
            "packageId": "pkg-123",
            "sourceEnv": "test",
            "targetEnv": "prod",
            "deployModes": [],
            "database": "dm",
        }
        result = generate_readme(manifest)
        assert "pkg-123" in result
        assert "-" in result


class TestGenerateImagesTxt:
    def test_basic_images_txt(self):
        image_entries = [
            {
                "group": "platform",
                "sourceRef": "registry.local/iam:1.0",
                "targetRef": "prod.registry/iam:1.0",
                "archiveFile": "prod.registry_iam_1.0.tar",
            },
            {
                "group": "business",
                "sourceRef": "registry.local/eam:2.0",
                "targetRef": "prod.registry/eam:2.0",
                "archiveFile": "prod.registry_eam_2.0.tar",
            },
        ]
        result = generate_images_txt(image_entries)
        assert "# group sourceRef targetRef archiveFile" in result
        assert "platform registry.local/iam:1.0 prod.registry/iam:1.0 prod.registry_iam_1.0.tar" in result
        assert "business registry.local/eam:2.0 prod.registry/eam:2.0 prod.registry_eam_2.0.tar" in result

    def test_empty_images_txt(self):
        result = generate_images_txt([])
        assert "# group sourceRef targetRef archiveFile" in result
        assert result.count("\n") == 1


class TestGeneratePullImagesScript:
    def test_basic_pull_script(self):
        image_entries = [
            {"sourceRef": "registry.local/iam:1.0"},
            {"sourceRef": "registry.local/eam:2.0"},
        ]
        result = generate_pull_images_script(image_entries)
        assert "#!/usr/bin/env bash" in result
        assert "set -euo pipefail" in result
        assert "docker pull registry.local/iam:1.0" in result
        assert "docker pull registry.local/eam:2.0" in result

    def test_empty_pull_script(self):
        result = generate_pull_images_script([])
        assert "#!/usr/bin/env bash" in result
        assert "set -euo pipefail" in result


class TestGenerateSaveImagesScript:
    def test_basic_save_script(self):
        image_entries = [
            {"sourceRef": "registry.local/iam:1.0", "archiveFile": "iam.tar"},
            {"sourceRef": "registry.local/eam:2.0", "archiveFile": "eam.tar"},
        ]
        result = generate_save_images_script(image_entries)
        assert "#!/usr/bin/env bash" in result
        assert "mkdir -p images/archives" in result
        assert "docker save -o images/archives/iam.tar registry.local/iam:1.0" in result
        assert "docker save -o images/archives/eam.tar registry.local/eam:2.0" in result


class TestGenerateLoadImagesScript:
    def test_load_script_with_tag(self):
        image_entries = [
            {
                "sourceRef": "registry.local/iam:1.0",
                "targetRef": "prod.registry/iam:1.0",
                "archiveFile": "iam.tar",
            },
        ]
        result = generate_load_images_script(image_entries)
        assert "#!/usr/bin/env bash" in result
        assert 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in result
        assert "docker load -i" in result
        assert "docker tag registry.local/iam:1.0 prod.registry/iam:1.0" in result

    def test_load_script_without_tag(self):
        image_entries = [
            {
                "sourceRef": "registry.local/iam:1.0",
                "targetRef": "registry.local/iam:1.0",
                "archiveFile": "iam.tar",
            },
        ]
        result = generate_load_images_script(image_entries)
        assert "docker load -i" in result
        assert "docker tag" not in result


class TestGenerateValidationSummary:
    def test_validation_summary_with_archives(self, tmp_path):
        package_root = tmp_path / "package"
        archive_dir = package_root / "images" / "archives"
        archive_dir.mkdir(parents=True)
        (archive_dir / "iam.tar").write_text("fake")
        (archive_dir / "eam.tar").write_text("fake")

        artifact_path = tmp_path / "artifact.tar.gz"
        artifact_path.write_text("fake artifact")

        package_index = {
            "summary": {
                "fileCount": 100,
                "totalBytes": 5000000,
            }
        }

        image_entries = [
            {"archiveFile": "iam.tar"},
            {"archiveFile": "eam.tar"},
            {"archiveFile": "missing.tar"},
        ]

        result = generate_validation_summary(
            package_root,
            artifact_path,
            package_index,
            image_entries,
            "image-archive",
        )

        assert result["artifactSize"] == len("fake artifact")
        assert result["packageIndexFileCount"] == 100
        assert result["packageIndexTotalBytes"] == 5000000
        assert result["imageEntryCount"] == 3
        assert result["imageArchiveCount"] == 2
        assert result["missingImageArchiveCount"] == 1

    def test_validation_summary_with_image_manifest_mode(self, tmp_path):
        package_root = tmp_path / "package"
        package_index = {"summary": {"fileCount": 10, "totalBytes": 1000}}
        image_entries = [{"archiveFile": "iam.tar"}]

        result = generate_validation_summary(
            package_root,
            None,
            package_index,
            image_entries,
            "image-manifest",
        )

        assert result["artifactSize"] == 0
        assert result["imageEntryCount"] == 1
        assert result["imageArchiveCount"] == 0
        assert result["missingImageArchiveCount"] == 0


class TestGeneratePackageIndex:
    def test_basic_package_index(self, tmp_path):
        package_root = tmp_path / "package"
        package_root.mkdir()
        (package_root / "k8s").mkdir(parents=True)
        (package_root / "k8s" / "deployment.yaml").write_text("fake")
        (package_root / "docker-compose").mkdir(parents=True)
        (package_root / "docker-compose" / "compose.yaml").write_text("fake")

        manifest = {
            "packageId": "pkg-123",
            "projectKey": "eam",
            "productVersion": "1.0",
            "deployModes": ["k8s"],
            "imageMode": "image-archive",
            "database": "postgresql",
        }

        result = generate_package_index(package_root, manifest)

        assert result["schemaVersion"] == "deployment-package-index/v1"
        assert result["packageId"] == "pkg-123"
        assert result["projectKey"] == "eam"
        assert result["productVersion"] == "1.0"
        assert "createdAt" in result
        assert result["summary"]["fileCount"] == 2
        assert result["summary"]["deployModes"] == ["k8s"]
        assert result["summary"]["imageMode"] == "image-archive"
        assert result["summary"]["database"] == "postgresql"
        assert "installer" in result
        assert "verifier" in result
        assert "qualityGate" in result
        assert "sections" in result
        assert "root" in result["sections"]
        assert "k8s" in result["sections"]
        assert "dockerCompose" in result["sections"]

    def test_package_index_with_default_project_key(self, tmp_path):
        package_root = tmp_path / "package"
        package_root.mkdir()
        (package_root / "README.md").write_text("fake")

        manifest = {
            "packageId": "pkg-123",
            "deployModes": [],
            "imageMode": "image-manifest",
            "database": "dm",
        }

        result = generate_package_index(package_root, manifest)
        assert result["projectKey"] == "custom"
        assert result["productVersion"] == ""


class TestGenerateFileIndexEntry:
    def test_file_in_subdirectory(self, tmp_path):
        package_root = tmp_path / "package"
        file_path = package_root / "k8s" / "deployment.yaml"
        file_path.parent.mkdir(parents=True)
        file_path.write_text("content")

        result = generate_file_index_entry(file_path, package_root)

        assert result["path"] == "k8s/deployment.yaml"
        assert result["size"] == len("content")
        assert "sha256" in result
        assert result["executable"] is False

    def test_file_in_root(self, tmp_path):
        package_root = tmp_path / "package"
        package_root.mkdir()
        file_path = package_root / "README.md"
        file_path.write_text("readme")

        result = generate_file_index_entry(file_path, package_root)

        assert result["path"] == "README.md"
        assert result["size"] == len("readme")
        assert "sha256" in result
        assert result["executable"] is False

    def test_shell_script_is_executable(self, tmp_path):
        package_root = tmp_path / "package"
        package_root.mkdir()
        file_path = package_root / "install.sh"
        file_path.write_text("#!/bin/bash\necho hello")

        result = generate_file_index_entry(file_path, package_root)

        assert result["path"] == "install.sh"
        assert result["executable"] is True


class TestExtractSection:
    def test_extract_matching_paths(self):
        files = [
            {"path": "README.md"},
            {"path": "manifest.json"},
            {"path": "k8s/deployment.yaml"},
        ]
        result = extract_section(files, {"README.md", "manifest.json"})
        assert len(result) == 2
        assert result[0]["path"] == "README.md"
        assert result[1]["path"] == "manifest.json"

    def test_extract_no_matches(self):
        files = [{"path": "k8s/deployment.yaml"}]
        result = extract_section(files, {"README.md"})
        assert len(result) == 0


class TestExtractSectionByPrefix:
    def test_extract_by_prefix(self):
        files = [
            {"path": "scripts/install.sh"},
            {"path": "scripts/verify.sh"},
            {"path": "docs/README.md"},
            {"path": "k8s/deployment.yaml"},
        ]
        result = extract_section_by_prefix(files, "scripts/")
        assert len(result) == 2
        assert result[0]["path"] == "scripts/install.sh"
        assert result[1]["path"] == "scripts/verify.sh"

    def test_extract_by_prefix_no_matches(self):
        files = [{"path": "k8s/deployment.yaml"}]
        result = extract_section_by_prefix(files, "scripts/")
        assert len(result) == 0
