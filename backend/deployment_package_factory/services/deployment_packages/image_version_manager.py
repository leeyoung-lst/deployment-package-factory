"""镜像版本管理和验证增强"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ImageMetadata:
    """增强的镜像元数据"""

    ref: str
    """镜像引用（repository:tag）"""

    digest: str = ""
    """镜像摘要（sha256:xxx）"""

    size_bytes: int = 0
    """镜像大小（字节）"""

    created_at: str = ""
    """创建时间（ISO 8601）"""

    architecture: str = ""
    """架构（amd64, arm64 等）"""

    os: str = ""
    """操作系统（linux, windows）"""

    version: str = ""
    """解析出的版本号"""

    labels: dict[str, str] | None = None
    """镜像标签"""

    layers_count: int = 0
    """镜像层数"""

    available: bool = True
    """镜像是否可用"""

    error_message: str = ""
    """错误消息（如果不可用）"""


@dataclass(frozen=True)
class VersionInfo:
    """版本信息"""

    major: int
    minor: int
    patch: int
    pre_release: str = ""
    """预发布版本（alpha, beta, rc 等）"""

    build_metadata: str = ""
    """构建元数据"""

    raw: str = ""
    """原始版本字符串"""

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            version += f"-{self.pre_release}"
        if self.build_metadata:
            version += f"+{self.build_metadata}"
        return version

    def is_stable(self) -> bool:
        """是否为稳定版本（无预发布标识）"""
        return not self.pre_release


VersionStatus = Literal["latest", "outdated", "deprecated", "unknown"]


@dataclass(frozen=True)
class VersionCheckResult:
    """版本检查结果"""

    current_version: str
    latest_version: str = ""
    status: VersionStatus = "unknown"
    recommendation: str = ""
    security_warning: str = ""


def parse_version(version_string: str) -> VersionInfo | None:
    """
    解析语义化版本号（Semantic Versioning）

    支持格式：
    - 1.2.3
    - 1.2 (默认 patch=0)
    - v1.2.3
    - 1.2.3-alpha
    - 1.2.3-beta.1
    - 1.2.3-rc.1+build.123

    Args:
        version_string: 版本字符串

    Returns:
        VersionInfo 对象，解析失败返回 None
    """
    # 移除前缀 'v'
    clean_version = version_string.strip().lstrip('v')

    # 尝试完整语义化版本正则（major.minor.patch）
    pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z\-\.]+))?(?:\+([0-9A-Za-z\-\.]+))?$'
    match = re.match(pattern, clean_version)

    if match:
        major, minor, patch, pre_release, build_metadata = match.groups()
    else:
        # 尝试简化版本（major.minor，默认 patch=0）
        pattern_short = r'^(\d+)\.(\d+)(?:-([0-9A-Za-z\-\.]+))?(?:\+([0-9A-Za-z\-\.]+))?$'
        match_short = re.match(pattern_short, clean_version)

        if not match_short:
            return None

        major, minor, pre_release, build_metadata = match_short.groups()
        patch = "0"  # 默认 patch 为 0

    return VersionInfo(
        major=int(major),
        minor=int(minor),
        patch=int(patch),
        pre_release=pre_release or "",
        build_metadata=build_metadata or "",
        raw=version_string,
    )


def extract_version_from_tag(image_tag: str) -> VersionInfo | None:
    """
    从镜像 tag 中提取版本号

    支持多种格式：
    - myapp:1.2.3
    - myapp:v1.2.3
    - myapp:1.2.3-alpine
    - myapp:20231201-1.2.3

    Args:
        image_tag: 镜像 tag（可能包含前缀或后缀）

    Returns:
        VersionInfo 对象，提取失败返回 None
    """
    # 常见版本号模式
    patterns = [
        r'v?(\d+\.\d+\.\d+(?:-[0-9A-Za-z\-\.]+)?(?:\+[0-9A-Za-z\-\.]+)?)',  # v1.2.3 或 1.2.3
        r'(\d{8})-v?(\d+\.\d+\.\d+)',  # 20231201-1.2.3（日期-版本）
    ]

    for pattern in patterns:
        match = re.search(pattern, image_tag)
        if match:
            version_str = match.group(1) if len(match.groups()) == 1 else match.group(2)
            return parse_version(version_str)

    return None


def compare_versions(v1: VersionInfo, v2: VersionInfo) -> int:
    """
    比较两个版本号

    Args:
        v1: 版本1
        v2: 版本2

    Returns:
        -1: v1 < v2
         0: v1 == v2
         1: v1 > v2
    """
    # 比较主版本号
    if v1.major != v2.major:
        return 1 if v1.major > v2.major else -1

    # 比较次版本号
    if v1.minor != v2.minor:
        return 1 if v1.minor > v2.minor else -1

    # 比较修订号
    if v1.patch != v2.patch:
        return 1 if v1.patch > v2.patch else -1

    # 比较预发布版本
    if v1.pre_release != v2.pre_release:
        # 有预发布版本的比没有的小
        if not v1.pre_release:
            return 1
        if not v2.pre_release:
            return -1
        # 字典序比较预发布版本
        return 1 if v1.pre_release > v2.pre_release else -1

    return 0


def inspect_image_with_skopeo(image_ref: str, insecure: bool = False) -> ImageMetadata:
    """
    使用 skopeo 检查镜像元数据

    Args:
        image_ref: 镜像引用（docker://registry/image:tag）
        insecure: 是否允许不安全的 HTTPS

    Returns:
        ImageMetadata 对象
    """
    import json

    # 确保使用 docker:// 前缀
    if not image_ref.startswith("docker://"):
        image_ref = f"docker://{image_ref}"

    cmd = ["skopeo", "inspect", image_ref]
    if insecure:
        cmd.append("--tls-verify=false")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout)

        # 提取版本号
        version = ""
        ref_without_prefix = image_ref.replace("docker://", "")
        if ":" in ref_without_prefix:
            tag = ref_without_prefix.split(":")[-1]
            version_info = extract_version_from_tag(tag)
            if version_info:
                version = str(version_info)

        return ImageMetadata(
            ref=ref_without_prefix,
            digest=data.get("Digest", ""),
            size_bytes=data.get("Size", 0),
            created_at=data.get("Created", ""),
            architecture=data.get("Architecture", ""),
            os=data.get("Os", ""),
            version=version,
            labels=data.get("Labels", {}),
            layers_count=len(data.get("Layers", [])),
            available=True,
        )
    except subprocess.CalledProcessError as e:
        return ImageMetadata(
            ref=image_ref.replace("docker://", ""),
            available=False,
            error_message=f"Failed to inspect image: {e.stderr or str(e)}",
        )
    except subprocess.TimeoutExpired:
        return ImageMetadata(
            ref=image_ref.replace("docker://", ""),
            available=False,
            error_message="Timeout while inspecting image",
        )
    except Exception as e:
        return ImageMetadata(
            ref=image_ref.replace("docker://", ""),
            available=False,
            error_message=f"Error: {str(e)}",
        )


def inspect_image_with_docker(image_ref: str) -> ImageMetadata:
    """
    使用 docker CLI 检查镜像元数据

    Args:
        image_ref: 镜像引用（registry/image:tag）

    Returns:
        ImageMetadata 对象
    """
    import json

    try:
        # 先尝试 pull 镜像（如果本地没有）
        subprocess.run(
            ["docker", "pull", image_ref],
            check=True,
            capture_output=True,
            timeout=300,
        )

        # 检查镜像
        result = subprocess.run(
            ["docker", "inspect", image_ref],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(result.stdout)[0]

        # 提取版本号
        version = ""
        if ":" in image_ref:
            tag = image_ref.split(":")[-1]
            version_info = extract_version_from_tag(tag)
            if version_info:
                version = str(version_info)

        return ImageMetadata(
            ref=image_ref,
            digest=data.get("RepoDigests", [""])[0].split("@")[-1] if data.get("RepoDigests") else "",
            size_bytes=data.get("Size", 0),
            created_at=data.get("Created", ""),
            architecture=data.get("Architecture", ""),
            os=data.get("Os", ""),
            version=version,
            labels=data.get("Config", {}).get("Labels") or {},
            layers_count=len(data.get("RootFS", {}).get("Layers", [])),
            available=True,
        )
    except subprocess.CalledProcessError as e:
        return ImageMetadata(
            ref=image_ref,
            available=False,
            error_message=f"Failed to inspect image: {e.stderr.decode() if e.stderr else str(e)}",
        )
    except subprocess.TimeoutExpired:
        return ImageMetadata(
            ref=image_ref,
            available=False,
            error_message="Timeout while inspecting image",
        )
    except Exception as e:
        return ImageMetadata(
            ref=image_ref,
            available=False,
            error_message=f"Error: {str(e)}",
        )


def inspect_image(image_ref: str, insecure: bool = False, prefer_skopeo: bool = True) -> ImageMetadata:
    """
    检查镜像元数据（自动选择工具）

    Args:
        image_ref: 镜像引用
        insecure: 是否允许不安全的 HTTPS
        prefer_skopeo: 优先使用 skopeo（更快，无需 Docker daemon）

    Returns:
        ImageMetadata 对象
    """
    import shutil

    if prefer_skopeo and shutil.which("skopeo"):
        return inspect_image_with_skopeo(image_ref, insecure)
    elif shutil.which("docker"):
        return inspect_image_with_docker(image_ref)
    else:
        return ImageMetadata(
            ref=image_ref,
            available=False,
            error_message="No image inspection tool available (skopeo or docker required)",
        )


def check_version_status(current_version: str, available_versions: list[str]) -> VersionCheckResult:
    """
    检查版本状态（是否过时、是否为最新等）

    Args:
        current_version: 当前版本
        available_versions: 可用版本列表

    Returns:
        VersionCheckResult 对象
    """
    current = parse_version(current_version)
    if not current:
        return VersionCheckResult(
            current_version=current_version,
            status="unknown",
            recommendation="无法解析版本号",
        )

    # 解析所有可用版本
    parsed_versions = []
    for v in available_versions:
        parsed = parse_version(v)
        if parsed:
            parsed_versions.append(parsed)

    if not parsed_versions:
        return VersionCheckResult(
            current_version=current_version,
            status="unknown",
            recommendation="无可用版本信息",
        )

    # 找到最新的稳定版本
    stable_versions = [v for v in parsed_versions if v.is_stable()]
    latest = max(stable_versions, key=lambda v: (v.major, v.minor, v.patch)) if stable_versions else None

    if not latest:
        return VersionCheckResult(
            current_version=current_version,
            latest_version="",
            status="unknown",
            recommendation="无稳定版本可用",
        )

    # 比较版本
    comparison = compare_versions(current, latest)

    if comparison == 0:
        return VersionCheckResult(
            current_version=current_version,
            latest_version=str(latest),
            status="latest",
            recommendation="已是最新稳定版本",
        )
    elif comparison < 0:
        # 当前版本较旧
        major_diff = latest.major - current.major
        minor_diff = latest.minor - current.minor

        if major_diff > 0:
            status = "deprecated" if major_diff >= 2 else "outdated"
            recommendation = f"建议升级到最新版本 {latest}（跨主版本升级，请注意兼容性）"
        elif minor_diff > 3:
            status = "outdated"
            recommendation = f"建议升级到最新版本 {latest}（当前版本较旧）"
        else:
            status = "outdated"
            recommendation = f"可升级到最新版本 {latest}"

        return VersionCheckResult(
            current_version=current_version,
            latest_version=str(latest),
            status=status,
            recommendation=recommendation,
        )
    else:
        # 当前版本较新（可能是预发布版本）
        return VersionCheckResult(
            current_version=current_version,
            latest_version=str(latest),
            status="unknown",
            recommendation=f"当前版本 {current} 比最新稳定版本 {latest} 更新（可能是预发布版本）",
        )


def format_size(size_bytes: int) -> str:
    """格式化字节大小为人类可读格式"""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.2f} {units[unit_index]}"
