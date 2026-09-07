"""镜像引用处理工具模块

提供镜像路径、标签、注册表等操作的辅助函数。
"""

from __future__ import annotations

import re

from deployment_package_factory.services.deployment_packages.errors import (
    PackageBuildError,
    validation_error,
)


def image_path_without_tag(image: str) -> str:
    """移除镜像引用中的注册表前缀和标签，返回纯镜像路径。

    Args:
        image: 镜像引用（可能包含注册表、标签、digest）

    Returns:
        移除注册表前缀和标签后的镜像路径

    Examples:
        >>> image_path_without_tag("registry.example.com/myapp/backend:v1.0")
        'myapp/backend'
        >>> image_path_without_tag("myapp/backend:latest")
        'myapp/backend'
        >>> image_path_without_tag("myapp/backend@sha256:abc123")
        'myapp/backend'
    """
    if has_registry(image):
        image = image.split("/", 1)[1]
    image = image.split("@", 1)[0]
    last_part = image.rsplit("/", 1)[-1]
    if ":" in last_part:
        return image.rsplit(":", 1)[0]
    return image


def has_registry(image: str) -> bool:
    """判断镜像引用是否包含注册表地址。

    Args:
        image: 镜像引用

    Returns:
        True 如果包含注册表地址，False 否则

    Examples:
        >>> has_registry("registry.example.com/myapp:v1")
        True
        >>> has_registry("localhost:5000/myapp:v1")
        True
        >>> has_registry("myapp:v1")
        False
    """
    if "/" not in image:
        return False
    first = image.split("/", 1)[0]
    return "." in first or ":" in first or first == "localhost"


def with_default_tag(image: str, default_tag: str) -> str:
    """为没有标签的镜像引用添加默认标签。

    Args:
        image: 镜像引用
        default_tag: 默认标签（当镜像没有标签时使用）

    Returns:
        带标签的镜像引用

    Raises:
        PackageBuildError: 如果镜像引用为空

    Examples:
        >>> with_default_tag("myapp", "prod")
        'myapp:prod'
        >>> with_default_tag("myapp:v1.0", "prod")
        'myapp:v1.0'
        >>> with_default_tag("myapp@sha256:abc", "prod")
        'myapp@sha256:abc'
    """
    image = image.strip()
    if not image:
        raise validation_error("镜像引用不能为空")
    last_part = image.rsplit("/", 1)[-1]
    if ":" in last_part or "@" in last_part:
        return image
    return f"{image}:{default_tag}"


def target_image_ref(source_ref: str, registry: str) -> str:
    """将源镜像引用转换为目标注册表的引用。

    移除源引用中的注册表前缀和项目前缀（如 local-ai/），
    然后添加目标注册表前缀。

    Args:
        source_ref: 源镜像引用
        registry: 目标注册表地址（可能包含项目路径）

    Returns:
        目标注册表的镜像引用

    Examples:
        >>> target_image_ref("myapp:v1", "registry.example.com/project")
        'registry.example.com/project/myapp:v1'
        >>> target_image_ref("local-ai/myapp:v1", "registry.example.com/project")
        'registry.example.com/project/myapp:v1'
    """
    if not registry:
        return source_ref
    if has_registry(source_ref):
        image_path = source_ref.split("/", 1)[1]
    else:
        image_path = source_ref
    registry_project = registry.rstrip("/").rsplit("/", 1)[-1]
    for project_prefix in (registry_project, "local-ai"):
        if project_prefix and image_path.startswith(f"{project_prefix}/"):
            image_path = image_path.removeprefix(f"{project_prefix}/")
            break
    return f"{registry}/{image_path}"


def safe_image_filename(image: str) -> str:
    """将镜像引用转换为安全的文件名。

    替换所有非字母数字字符为下划线。

    Args:
        image: 镜像引用

    Returns:
        安全的文件名

    Examples:
        >>> safe_image_filename("registry.example.com/myapp:v1.0")
        'registry.example.com_myapp_v1.0'
    """
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", image).strip("_")


def normalize_image_id(image_id: str) -> str:
    """规范化镜像 ID，移除协议前缀。

    Args:
        image_id: 原始镜像 ID（可能包含 docker-pullable:// 等前缀）

    Returns:
        规范化后的镜像 ID

    Examples:
        >>> normalize_image_id("docker-pullable://myapp@sha256:abc")
        'myapp@sha256:abc'
        >>> normalize_image_id("containerd://myapp@sha256:abc")
        'myapp@sha256:abc'
    """
    for prefix in ("docker-pullable://", "containerd://", "docker://"):
        if image_id.startswith(prefix):
            return image_id.removeprefix(prefix)
    return image_id


def split_image_tag(image: str) -> tuple[str, str]:
    """分割镜像引用为路径和标签。

    Args:
        image: 镜像引用

    Returns:
        (镜像路径, 标签) 元组，如果没有标签则标签为空字符串

    Examples:
        >>> split_image_tag("myapp:v1.0")
        ('myapp', 'v1.0')
        >>> split_image_tag("registry.example.com/myapp:latest")
        ('registry.example.com/myapp', 'latest')
        >>> split_image_tag("myapp")
        ('myapp', '')
    """
    image = image.split("@", 1)[0]
    last_part = image.rsplit("/", 1)[-1]
    if ":" not in last_part:
        return image, ""
    path, tag = image.rsplit(":", 1)
    return path, tag


def image_registry_priority(image: str) -> int:
    """返回镜像引用的注册表优先级。

    有注册表前缀的镜像优先级为 1，否则为 0。
    用于镜像匹配时的优先级排序。

    Args:
        image: 镜像引用

    Returns:
        优先级值（1 或 0）
    """
    return 1 if has_registry(image) else 0


def source_registry_host(source_ref: str) -> str:
    """从镜像引用中提取注册表主机名。

    Args:
        source_ref: 镜像引用

    Returns:
        注册表主机名，如果没有则返回空字符串

    Examples:
        >>> source_registry_host("registry.example.com:5000/myapp:v1")
        'registry.example.com:5000'
        >>> source_registry_host("myapp:v1")
        ''
    """
    if not has_registry(source_ref):
        return ""
    return source_ref.split("/", 1)[0]


def runtime_image_match_score(catalog_ref: str, runtime_ref: str) -> int:
    """计算运行时镜像与目录镜像的匹配度分数。

    Args:
        catalog_ref: 目录镜像引用
        runtime_ref: 运行时镜像引用

    Returns:
        匹配度分数：
        - 100: 完全匹配
        - 80: 基础名称匹配
        - 70: 运行时镜像是 local-ai- 前缀版本
        - 60: 目录镜像是 local-ai- 前缀版本
        - 0: 不匹配
    """
    expected_path = image_path_without_tag(catalog_ref)
    runtime_path = image_path_without_tag(runtime_ref)
    expected_base = expected_path.rsplit("/", 1)[-1]
    runtime_base = runtime_path.rsplit("/", 1)[-1]
    if runtime_path == expected_path:
        return 100
    if runtime_base == expected_base:
        return 80
    if runtime_base == f"local-ai-{expected_base}":
        return 70
    if expected_base.startswith("local-ai-") and runtime_base == expected_base.removeprefix("local-ai-"):
        return 60
    return 0


def matches_catalog_image(catalog_images: list[str], runtime_ref: str, default_tag: str = "prod") -> bool:
    """检查运行时镜像引用是否匹配目录中的任一镜像。

    Args:
        catalog_images: 目录镜像列表
        runtime_ref: 运行时镜像引用
        default_tag: 默认标签

    Returns:
        True 如果匹配，False 否则
    """
    for image in catalog_images:
        if runtime_image_match_score(with_default_tag(image, default_tag), runtime_ref) > 0:
            return True
    return False
