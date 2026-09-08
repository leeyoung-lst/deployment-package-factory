"""文件内容生成工具模块

提供部署包中各种文本文件内容的生成函数，包括：
- README 文档
- 镜像清单和脚本
- 包索引和验证摘要
- 文件索引条目
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from deployment_package_factory.services.deployment_packages.install_renderer import INSTALLER_OPTIONS, INSTALLER_VERSION
from deployment_package_factory.services.deployment_packages.quality_renderer import QUALITY_GATE_CHECKS, QUALITY_GATE_VERSION
from deployment_package_factory.services.deployment_packages.verify_renderer import VERIFIER_VERSION


def generate_readme(manifest: dict) -> str:
    """生成 README.md 内容

    Args:
        manifest: 包清单字典

    Returns:
        README 文本内容
    """
    return f"""# Local AI 生产部署包

包编号：`{manifest["packageId"]}`

来源环境：`{manifest["sourceEnv"]}`

目标环境：`{manifest["targetEnv"]}`

部署方式：{", ".join(manifest["deployModes"]) or "-"}

数据库：`{manifest["database"]}`

安装前质量门禁：

```bash
./quality-gate.sh
```

质量报告：`docs/quality-report.md`

"""


def generate_images_txt(image_entries: list[dict]) -> str:
    """生成镜像清单文本

    Args:
        image_entries: 镜像条目列表

    Returns:
        镜像清单文本内容
    """
    lines = ["# group sourceRef targetRef archiveFile"]
    lines.extend(
        f"{item['group']} {item['sourceRef']} {item['targetRef']} {item['archiveFile']}"
        for item in image_entries
    )
    return "\n".join(lines) + "\n"


def generate_pull_images_script(image_entries: list[dict]) -> str:
    """生成拉取镜像脚本

    Args:
        image_entries: 镜像条目列表

    Returns:
        拉取脚本内容
    """
    commands = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    commands.extend(f"docker pull {item['sourceRef']}" for item in image_entries)
    return "\n".join(commands) + "\n"


def generate_save_images_script(image_entries: list[dict]) -> str:
    """生成保存镜像脚本

    Args:
        image_entries: 镜像条目列表

    Returns:
        保存脚本内容
    """
    commands = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "mkdir -p images/archives",
        "",
    ]
    commands.extend(
        f"docker save -o images/archives/{item['archiveFile']} {item['sourceRef']}"
        for item in image_entries
    )
    return "\n".join(commands) + "\n"


def generate_load_images_script(image_entries: list[dict]) -> str:
    """生成加载镜像脚本

    Args:
        image_entries: 镜像条目列表

    Returns:
        加载脚本内容
    """
    commands = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"',
        "",
    ]
    for item in image_entries:
        archive = f"${{PACKAGE_ROOT}}/images/archives/{item['archiveFile']}"
        commands.append(f"docker load -i {archive}")
        if item["sourceRef"] != item["targetRef"]:
            commands.append(f"docker tag {item['sourceRef']} {item['targetRef']}")
    return "\n".join(commands) + "\n"


def generate_validation_summary(
    package_root: Path,
    artifact_path: Path | None,
    package_index: dict,
    image_entries: list[dict],
    image_mode: str,
) -> dict:
    """生成验证摘要

    Args:
        package_root: 包根目录
        artifact_path: 产物路径
        package_index: 包索引
        image_entries: 镜像条目列表
        image_mode: 镜像模式

    Returns:
        验证摘要字典
    """
    archive_dir = package_root / "images" / "archives"
    archive_files = {
        path.name
        for path in archive_dir.iterdir()
        if path.is_file() and path.name != ".gitkeep"
    } if archive_dir.exists() else set()
    expected_archives = {item["archiveFile"] for item in image_entries} if image_mode == "image-archive" else set()
    return {
        "artifactSize": artifact_path.stat().st_size if artifact_path and artifact_path.exists() else 0,
        "packageIndexFileCount": package_index.get("summary", {}).get("fileCount", 0),
        "packageIndexTotalBytes": package_index.get("summary", {}).get("totalBytes", 0),
        "imageEntryCount": len(image_entries),
        "imageArchiveCount": len(archive_files),
        "missingImageArchiveCount": len(expected_archives - archive_files),
    }


def generate_package_index(package_root: Path, manifest: dict) -> dict:
    """生成包索引

    Args:
        package_root: 包根目录
        manifest: 包清单

    Returns:
        包索引字典
    """
    files = [generate_file_index_entry(path, package_root) for path in sorted(item for item in package_root.rglob("*") if item.is_file())]
    return {
        "schemaVersion": "deployment-package-index/v1",
        "packageId": manifest["packageId"],
        "projectKey": manifest.get("projectKey") or "custom",
        "productVersion": manifest.get("productVersion") or "",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "fileCount": len(files),
            "totalBytes": sum(item["size"] for item in files),
            "deployModes": manifest["deployModes"],
            "imageMode": manifest["imageMode"],
            "database": manifest["database"],
        },
        "installer": {
            "version": INSTALLER_VERSION,
            "entrypoints": ["install.sh", "install.ps1"],
            "supportedModes": ["k8s", "docker-compose"],
            "options": INSTALLER_OPTIONS,
            "successChecks": ["health-check", "diagnostics"],
        },
        "verifier": {
            "version": VERIFIER_VERSION,
            "entrypoints": ["verify.sh", "verify.ps1"],
            "checks": ["required-files", "sha256sums", "package-index", "image-archive-lock"],
        },
        "qualityGate": {
            "version": QUALITY_GATE_VERSION,
            "entrypoints": ["quality-gate.sh", "quality-gate.ps1"],
            "checks": QUALITY_GATE_CHECKS,
            "report": "docs/quality-report.runtime.md",
            "template": "docs/quality-report.md",
        },
        "acceptance": {
            "report": "docs/acceptance-report.md",
        },
        "sections": {
            "root": extract_section(
                files,
                {
                    "README.md",
                    "manifest.json",
                    "package-index.json",
                    "install.sh",
                    "install.ps1",
                    "verify.sh",
                    "verify.ps1",
                    "quality-gate.sh",
                    "quality-gate.ps1",
                    "deploy-values.json",
                },
            ),
            "docs": extract_section_by_prefix(files, "docs/"),
            "k8s": extract_section_by_prefix(files, "k8s/"),
            "dockerCompose": extract_section_by_prefix(files, "docker-compose/"),
            "init": extract_section_by_prefix(files, "init/"),
            "overlays": extract_section_by_prefix(files, "overlays/"),
            "images": extract_section_by_prefix(files, "images/"),
            "scripts": extract_section_by_prefix(files, "scripts/"),
            "security": extract_section_by_prefix(files, "security/"),
        },
    }


def generate_file_index_entry(path: Path, package_root: Path) -> dict:
    """生成文件索引条目

    Args:
        path: 文件路径
        package_root: 包根目录

    Returns:
        文件索引条目字典
    """
    rel = path.relative_to(package_root).as_posix()
    return {
        "path": rel,
        "size": path.stat().st_size,
        "sha256": _file_sha256(path),
        "executable": path.suffix == ".sh",
    }


def extract_section(files: list[dict], paths: set[str]) -> list[dict]:
    """提取指定路径的文件

    Args:
        files: 文件列表
        paths: 路径集合

    Returns:
        匹配的文件列表
    """
    return [item for item in files if item["path"] in paths]


def extract_section_by_prefix(files: list[dict], prefix: str) -> list[dict]:
    """按前缀提取文件

    Args:
        files: 文件列表
        prefix: 路径前缀

    Returns:
        匹配的文件列表
    """
    return [item for item in files if item["path"].startswith(prefix)]


def _file_sha256(path: Path) -> str:
    """计算文件的 SHA256 哈希值

    Args:
        path: 文件路径

    Returns:
        SHA256 哈希值（十六进制字符串）
    """
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
