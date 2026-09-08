"""测试配置文件预览功能"""
import json
from pathlib import Path

import pytest

from deployment_package_factory.services.deployment_packages.preview_service import (
    detect_language,
    get_package_root_from_task,
    preview_package_files,
    PREVIEWABLE_FILES,
)
from deployment_package_factory.services.deployment_packages.preview_models import PackagePreviewResponse


def test_detect_language():
    """测试语言检测"""
    assert detect_language("manifest.json") == "json"
    assert detect_language("namespace.yaml") == "yaml"
    assert detect_language("namespace.yml") == "yaml"
    assert detect_language("script.sh") == "shell"
    assert detect_language("script.bash") == "shell"
    assert detect_language("schema.sql") == "sql"
    assert detect_language("README.md") == "markdown"
    assert detect_language("README.markdown") == "markdown"
    assert detect_language("unknown.txt") == "text"


def test_preview_package_files_with_real_package(tmp_path: Path):
    """测试预览真实部署包的配置文件"""
    # 创建模拟的部署包目录结构
    package_root = tmp_path / "local-ai-prod-package-pkg-20260908-abc123"
    package_root.mkdir()

    # 创建测试文件
    manifest = {
        "packageId": "pkg-20260908-abc123",
        "projectKey": "test",
        "sourceEnv": "dev",
        "targetEnv": "prod",
    }
    (package_root / "manifest.json").write_text(json.dumps(manifest, indent=2))

    readme = "# 部署包 README\n\n这是测试部署包。"
    (package_root / "README.md").write_text(readme)

    (package_root / "images").mkdir()
    images_txt = "registry.example.com/app:latest\nregistry.example.com/db:14\n"
    (package_root / "images" / "images.txt").write_text(images_txt)

    (package_root / "k8s").mkdir()
    namespace_yaml = "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: test\n"
    (package_root / "k8s" / "namespace.yaml").write_text(namespace_yaml)

    # 预览文件（只请求存在的文件）
    result = preview_package_files(
        package_root,
        requested_files=["manifest.json", "README.md", "images/images.txt", "k8s/namespace.yaml"],
    )

    assert isinstance(result, PackagePreviewResponse)
    assert result.package_id == "pkg-20260908-abc123"
    assert len(result.files) == 4

    # 验证 manifest.json
    manifest_file = next(f for f in result.files if f.path == "manifest.json")
    assert manifest_file.language == "json"
    assert '"packageId"' in manifest_file.content
    assert not manifest_file.truncated

    # 验证 README.md
    readme_file = next(f for f in result.files if f.path == "README.md")
    assert readme_file.language == "markdown"
    assert "部署包 README" in readme_file.content
    assert not readme_file.truncated

    # 验证 images.txt
    images_file = next(f for f in result.files if f.path == "images/images.txt")
    assert images_file.language == "text"
    assert "registry.example.com/app:latest" in images_file.content

    # 验证 namespace.yaml
    ns_file = next(f for f in result.files if f.path == "k8s/namespace.yaml")
    assert ns_file.language == "yaml"
    assert "Namespace" in ns_file.content


def test_preview_package_files_defaults_to_first_five(tmp_path: Path):
    """测试默认预览前5个文件"""
    package_root = tmp_path / "local-ai-prod-package-pkg-test"
    package_root.mkdir()

    # 创建多个可预览文件
    (package_root / "manifest.json").write_text('{"test": true}')
    (package_root / "README.md").write_text("# README")
    (package_root / "package-index.json").write_text('{"files": []}')

    (package_root / "images").mkdir()
    (package_root / "images" / "images.txt").write_text("image:latest")

    (package_root / "k8s").mkdir()
    (package_root / "k8s" / "namespace.yaml").write_text("kind: Namespace")

    # 不指定文件列表，应该预览默认的前5个
    result = preview_package_files(package_root, requested_files=None)

    assert len(result.files) <= 5
    assert any(f.path == "manifest.json" for f in result.files)


def test_preview_package_files_handles_missing_files(tmp_path: Path):
    """测试处理不存在的文件"""
    package_root = tmp_path / "local-ai-prod-package-pkg-test"
    package_root.mkdir()

    # 只创建一个文件
    (package_root / "manifest.json").write_text('{"test": true}')

    # 请求多个文件，其中一些不存在
    result = preview_package_files(
        package_root,
        requested_files=["manifest.json", "README.md", "non-existent.txt"],
    )

    # 应该只返回存在的文件
    assert len(result.files) == 1
    assert result.files[0].path == "manifest.json"


def test_preview_package_files_truncates_large_files(tmp_path: Path):
    """测试大文件被截断"""
    package_root = tmp_path / "local-ai-prod-package-pkg-test"
    package_root.mkdir()

    # 创建一个超过 500KB 的大文件
    large_content = "x" * (600 * 1024)  # 600 KB
    (package_root / "manifest.json").write_text(large_content)

    result = preview_package_files(package_root, requested_files=["manifest.json"])

    assert len(result.files) == 1
    file = result.files[0]
    assert file.truncated is True
    assert len(file.content) < len(large_content)
    assert "文件过大，已截断" in file.content


def test_preview_package_files_lists_available_files(tmp_path: Path):
    """测试列出所有可预览的文件"""
    package_root = tmp_path / "local-ai-prod-package-pkg-test"
    package_root.mkdir()

    # 创建部分 PREVIEWABLE_FILES 中的文件
    (package_root / "manifest.json").write_text('{}')
    (package_root / "README.md").write_text('# README')

    (package_root / "images").mkdir()
    (package_root / "images" / "images.txt").write_text('')

    result = preview_package_files(package_root, requested_files=["manifest.json"])

    # available_files 应该包含所有存在的可预览文件
    assert "manifest.json" in result.available_files
    assert "README.md" in result.available_files
    assert "images/images.txt" in result.available_files
    assert "k8s/namespace.yaml" not in result.available_files  # 这个不存在


def test_preview_package_files_raises_on_nonexistent_package(tmp_path: Path):
    """测试部署包目录不存在时抛出异常"""
    non_existent = tmp_path / "does-not-exist"

    with pytest.raises(FileNotFoundError):
        preview_package_files(non_existent)


def test_get_package_root_from_task(tmp_path: Path):
    """测试从任务结果中获取部署包根目录"""
    work_dir = tmp_path / "work" / "pkg-20260908-abc123"
    work_dir.mkdir(parents=True)

    package_root = work_dir / "local-ai-prod-package-pkg-20260908-abc123"
    package_root.mkdir()

    task_result = {
        "workDir": str(work_dir),
        "artifactPath": str(tmp_path / "artifacts" / "package.tar.gz"),
    }

    result = get_package_root_from_task(task_result)

    assert result == package_root


def test_get_package_root_from_task_returns_none_for_missing_work_dir():
    """测试工作目录不存在时返回 None"""
    task_result = {
        "workDir": "/does/not/exist",
    }

    result = get_package_root_from_task(task_result)

    assert result is None


def test_get_package_root_from_task_returns_none_for_invalid_result():
    """测试任务结果无效时返回 None"""
    assert get_package_root_from_task(None) is None
    assert get_package_root_from_task({}) is None
    assert get_package_root_from_task({"other": "field"}) is None


def test_previewable_files_list_is_comprehensive():
    """测试可预览文件列表包含所有关键配置"""
    # 验证列表包含关键文件类型
    assert "manifest.json" in PREVIEWABLE_FILES
    assert "README.md" in PREVIEWABLE_FILES
    assert "package-index.json" in PREVIEWABLE_FILES

    # K8s 配置
    assert any("k8s/" in f for f in PREVIEWABLE_FILES)

    # Docker Compose 配置
    assert any("docker-compose/" in f for f in PREVIEWABLE_FILES)

    # 镜像相关
    assert any("images/" in f for f in PREVIEWABLE_FILES)

    # 初始化脚本
    assert any("init/" in f for f in PREVIEWABLE_FILES)

    # 安全相关
    assert "security/SHA256SUMS" in PREVIEWABLE_FILES
