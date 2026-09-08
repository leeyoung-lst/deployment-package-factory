"""部署包配置文件预览服务"""
from pathlib import Path
from typing import Literal

from deployment_package_factory.services.deployment_packages.preview_models import PackagePreviewResponse, PreviewFile


# 最大预览文件大小（500 KB）
MAX_PREVIEW_SIZE = 500 * 1024

# 可预览的文件路径列表（相对于部署包根目录）
PREVIEWABLE_FILES = [
    "manifest.json",
    "README.md",
    "package-index.json",
    "images/images.txt",
    "k8s/namespace.yaml",
    "k8s/configmap.yaml",
    "k8s/secrets.template.yaml",
    "k8s/deployments.yaml",
    "k8s/services.yaml",
    "k8s/ingress.yaml",
    "docker-compose/docker-compose.yml",
    "docker-compose/.env.template",
    "scripts/pull-images.sh",
    "scripts/save-images.sh",
    "scripts/load-images.sh",
    "init/postgres/001_schema.sql",
    "init/minio/create-buckets.sh",
    "init/qdrant/create-collections.sh",
    "security/SHA256SUMS",
]


def detect_language(file_path: str) -> Literal["yaml", "json", "shell", "sql", "markdown", "text"]:
    """根据文件扩展名检测语法高亮语言"""
    lower_path = file_path.lower()
    if lower_path.endswith((".yaml", ".yml")):
        return "yaml"
    if lower_path.endswith(".json"):
        return "json"
    if lower_path.endswith((".sh", ".bash")):
        return "shell"
    if lower_path.endswith(".sql"):
        return "sql"
    if lower_path.endswith((".md", ".markdown")):
        return "markdown"
    return "text"


def preview_package_files(package_root: Path, requested_files: list[str] | None = None) -> PackagePreviewResponse:
    """
    预览部署包中的配置文件

    Args:
        package_root: 部署包根目录
        requested_files: 请求预览的文件列表（相对路径），如果为 None 则预览默认文件

    Returns:
        PackagePreviewResponse 包含文件内容和元数据

    Raises:
        FileNotFoundError: 如果 package_root 不存在
    """
    if not package_root.exists():
        raise FileNotFoundError(f"Package root does not exist: {package_root}")

    package_id = package_root.name.replace("local-ai-prod-package-", "")

    # 确定要预览的文件列表
    files_to_preview = requested_files if requested_files else PREVIEWABLE_FILES[:5]  # 默认前5个

    # 收集可用的文件列表
    available_files = []
    for file_path in PREVIEWABLE_FILES:
        full_path = package_root / file_path
        if full_path.exists() and full_path.is_file():
            available_files.append(file_path)

    # 读取文件内容
    preview_files = []
    for file_path in files_to_preview:
        full_path = package_root / file_path
        if not full_path.exists() or not full_path.is_file():
            continue

        file_size = full_path.stat().st_size
        truncated = file_size > MAX_PREVIEW_SIZE

        try:
            if truncated:
                # 如果文件过大，只读取前 MAX_PREVIEW_SIZE 字节
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read(MAX_PREVIEW_SIZE)
                content += f"\n\n... (文件过大，已截断。完整文件大小: {file_size} 字节)"
            else:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

            preview_files.append(
                PreviewFile(
                    path=file_path,
                    content=content,
                    language=detect_language(file_path),
                    size=file_size,
                    truncated=truncated,
                )
            )
        except Exception:
            # 忽略无法读取的文件
            continue

    return PackagePreviewResponse(
        package_id=package_id,
        files=preview_files,
        available_files=available_files,
    )


def get_package_root_from_task(task_result: dict) -> Path | None:
    """
    从任务结果中获取部署包根目录

    Args:
        task_result: PackageTask.result 字典

    Returns:
        部署包根目录的 Path，如果不存在则返回 None
    """
    if not task_result or "workDir" not in task_result:
        return None

    work_dir = Path(task_result["workDir"])
    if not work_dir.exists():
        return None

    # 查找部署包目录（local-ai-prod-package-*）
    package_dirs = list(work_dir.glob("local-ai-prod-package-*"))
    if not package_dirs:
        return None

    return package_dirs[0]
