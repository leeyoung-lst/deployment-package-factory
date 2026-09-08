"""测试增量更新功能"""
import json
import tempfile
from pathlib import Path

import pytest

from deployment_package_factory.services.deployment_packages.delta_package import (
    compute_package_diff,
    create_delta_package,
    apply_delta_package,
    generate_delta_manifest,
)


@pytest.fixture
def base_package(tmp_path):
    """创建基础包"""
    base_dir = tmp_path / "base-package"
    base_dir.mkdir()

    # 创建清单
    manifest = {
        "packageId": "pkg-base-001",
        "projectKey": "test",
        "productVersion": "1.0.0",
    }
    (base_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # 创建文件
    (base_dir / "file1.txt").write_text("content1", encoding="utf-8")
    (base_dir / "file2.txt").write_text("content2", encoding="utf-8")
    (base_dir / "file3.txt").write_text("content3", encoding="utf-8")

    return base_dir


@pytest.fixture
def target_package(tmp_path):
    """创建目标包"""
    target_dir = tmp_path / "target-package"
    target_dir.mkdir()

    # 创建清单
    manifest = {
        "packageId": "pkg-target-002",
        "projectKey": "test",
        "productVersion": "2.0.0",
    }
    (target_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # file1: 修改
    (target_dir / "file1.txt").write_text("content1-modified", encoding="utf-8")
    # file2: 未变更
    (target_dir / "file2.txt").write_text("content2", encoding="utf-8")
    # file3: 删除（不创建）
    # file4: 新增
    (target_dir / "file4.txt").write_text("content4", encoding="utf-8")

    return target_dir


def test_compute_package_diff_detects_changes(base_package, target_package):
    """测试差异检测"""
    diff = compute_package_diff(base_package, target_package)

    assert diff.base_package_id == "pkg-base-001"
    assert diff.target_package_id == "pkg-target-002"

    # 新增文件
    assert len(diff.added_files) == 1
    assert diff.added_files[0].path == "file4.txt"
    assert diff.added_files[0].change_type == "added"

    # 修改文件
    assert len(diff.modified_files) == 1
    assert diff.modified_files[0].path == "file1.txt"
    assert diff.modified_files[0].change_type == "modified"

    # 删除文件
    assert len(diff.deleted_files) == 1
    assert diff.deleted_files[0].path == "file3.txt"
    assert diff.deleted_files[0].change_type == "deleted"

    # 未变更文件
    assert len(diff.unchanged_files) == 1
    assert diff.unchanged_files[0].path == "file2.txt"


def test_compute_package_diff_no_changes(base_package):
    """测试无变更的情况"""
    diff = compute_package_diff(base_package, base_package)

    assert len(diff.added_files) == 0
    assert len(diff.modified_files) == 0
    assert len(diff.deleted_files) == 0
    assert len(diff.unchanged_files) == 3  # file1, file2, file3
    assert diff.has_changes is False


def test_diff_calculates_sizes(base_package, target_package):
    """测试大小计算"""
    diff = compute_package_diff(base_package, target_package)

    assert diff.total_old_size > 0
    assert diff.total_new_size > 0
    assert diff.delta_size > 0


def test_change_summary(base_package, target_package):
    """测试变更摘要"""
    diff = compute_package_diff(base_package, target_package)
    summary = diff.change_summary

    assert summary["added"] == 1
    assert summary["modified"] == 1
    assert summary["deleted"] == 1
    assert summary["unchanged"] == 1
    assert summary["totalFiles"] == 4
    assert "deltaSize" in summary
    assert "compressionRatio" in summary


def test_generate_delta_manifest(base_package, target_package):
    """测试生成增量清单"""
    diff = compute_package_diff(base_package, target_package)
    target_manifest = json.loads((target_package / "manifest.json").read_text())

    delta_manifest = generate_delta_manifest(diff, target_manifest)

    assert delta_manifest["deltaPackage"] is True
    assert delta_manifest["basePackageId"] == "pkg-base-001"
    assert delta_manifest["targetPackageId"] == "pkg-target-002"
    assert "file4.txt" in delta_manifest["addedFiles"]
    assert "file1.txt" in delta_manifest["modifiedFiles"]
    assert "file3.txt" in delta_manifest["deletedFiles"]


def test_create_delta_package(base_package, target_package, tmp_path):
    """测试创建增量包"""
    output_dir = tmp_path / "delta-output"
    output_dir.mkdir()

    delta_package_dir = create_delta_package(base_package, target_package, output_dir)

    # 验证增量包结构
    assert delta_package_dir.exists()
    assert (delta_package_dir / "delta-manifest.json").exists()
    assert (delta_package_dir / "README.md").exists()
    assert (delta_package_dir / "apply-delta.sh").exists()
    assert (delta_package_dir / "DELETED_FILES.txt").exists()

    # 验证新增和修改的文件被复制
    assert (delta_package_dir / "file1.txt").exists()
    assert (delta_package_dir / "file4.txt").exists()

    # 验证未变更的文件不被复制
    assert not (delta_package_dir / "file2.txt").exists()


def test_create_delta_package_raises_on_no_changes(base_package, tmp_path):
    """测试无变更时抛出异常"""
    output_dir = tmp_path / "delta-output"
    output_dir.mkdir()

    with pytest.raises(ValueError, match="No changes detected"):
        create_delta_package(base_package, base_package, output_dir)


def test_apply_delta_package(base_package, target_package, tmp_path):
    """测试应用增量包"""
    # 创建增量包
    delta_output = tmp_path / "delta-output"
    delta_output.mkdir()
    delta_package_dir = create_delta_package(base_package, target_package, delta_output)

    # 应用增量包
    result_dir = apply_delta_package(base_package, delta_package_dir)

    # 验证结果
    assert result_dir.exists()
    assert (result_dir / "file1.txt").read_text(encoding="utf-8") == "content1-modified"  # 修改
    assert (result_dir / "file2.txt").read_text(encoding="utf-8") == "content2"  # 未变更
    assert not (result_dir / "file3.txt").exists()  # 删除
    assert (result_dir / "file4.txt").read_text(encoding="utf-8") == "content4"  # 新增


def test_apply_delta_package_validates_base_id(base_package, target_package, tmp_path):
    """测试应用增量包时验证基础包 ID"""
    # 创建增量包
    delta_output = tmp_path / "delta-output"
    delta_output.mkdir()
    delta_package_dir = create_delta_package(base_package, target_package, delta_output)

    # 修改基础包的 ID
    wrong_base = tmp_path / "wrong-base"
    wrong_base.mkdir()
    manifest = {"packageId": "pkg-wrong-999"}
    (wrong_base / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # 应该抛出异常
    with pytest.raises(ValueError, match="Base package mismatch"):
        apply_delta_package(wrong_base, delta_package_dir)


def test_delta_readme_generated(base_package, target_package, tmp_path):
    """测试增量包 README 生成"""
    output_dir = tmp_path / "delta-output"
    output_dir.mkdir()
    delta_package_dir = create_delta_package(base_package, target_package, output_dir)

    readme_content = (delta_package_dir / "README.md").read_text(encoding="utf-8")

    assert "增量更新包" in readme_content
    assert "pkg-base-001" in readme_content
    assert "pkg-target-002" in readme_content
    assert "新增文件" in readme_content
    assert "修改文件" in readme_content
    assert "删除文件" in readme_content


def test_apply_script_generated(base_package, target_package, tmp_path):
    """测试应用脚本生成"""
    output_dir = tmp_path / "delta-output"
    output_dir.mkdir()
    delta_package_dir = create_delta_package(base_package, target_package, output_dir)

    script_path = delta_package_dir / "apply-delta.sh"
    assert script_path.exists()
    assert script_path.stat().st_mode & 0o111  # 可执行


def test_deleted_files_list_generated(base_package, target_package, tmp_path):
    """测试删除文件列表生成"""
    output_dir = tmp_path / "delta-output"
    output_dir.mkdir()
    delta_package_dir = create_delta_package(base_package, target_package, output_dir)

    deleted_files = (delta_package_dir / "DELETED_FILES.txt").read_text(encoding="utf-8")
    assert "file3.txt" in deleted_files


def test_diff_excludes_manifest(base_package, target_package):
    """测试排除 manifest.json"""
    diff = compute_package_diff(base_package, target_package)

    # manifest.json 应该被排除，不出现在任何变更列表中
    all_paths = [f.path for f in diff.added_files + diff.modified_files + diff.deleted_files + diff.unchanged_files]
    assert "manifest.json" not in all_paths


def test_compression_ratio_calculation(base_package, target_package):
    """测试压缩率计算"""
    diff = compute_package_diff(base_package, target_package)
    summary = diff.change_summary

    # 压缩率应该在 0-100 之间
    assert 0 <= summary["compressionRatio"] <= 100
