"""增量更新支持 - 部署包差异分析和增量包生成"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


ChangeType = Literal["added", "modified", "deleted", "unchanged"]


@dataclass(frozen=True)
class FileChange:
    """文件变更信息"""

    path: str
    """文件路径（相对于包根目录）"""

    change_type: ChangeType
    """变更类型"""

    old_size: int = 0
    """旧文件大小（字节）"""

    new_size: int = 0
    """新文件大小（字节）"""

    old_hash: str = ""
    """旧文件 SHA256"""

    new_hash: str = ""
    """新文件 SHA256"""


@dataclass(frozen=True)
class PackageDiff:
    """部署包差异信息"""

    base_package_id: str
    """基础包 ID"""

    target_package_id: str
    """目标包 ID"""

    added_files: list[FileChange]
    """新增文件"""

    modified_files: list[FileChange]
    """修改文件"""

    deleted_files: list[FileChange]
    """删除文件"""

    unchanged_files: list[FileChange]
    """未变更文件"""

    total_old_size: int
    """旧包总大小"""

    total_new_size: int
    """新包总大小"""

    delta_size: int
    """增量大小（新增 + 修改）"""

    @property
    def has_changes(self) -> bool:
        """是否有变更"""
        return len(self.added_files) > 0 or len(self.modified_files) > 0 or len(self.deleted_files) > 0

    @property
    def change_summary(self) -> dict:
        """变更摘要"""
        return {
            "added": len(self.added_files),
            "modified": len(self.modified_files),
            "deleted": len(self.deleted_files),
            "unchanged": len(self.unchanged_files),
            "totalFiles": len(self.added_files) + len(self.modified_files) + len(self.deleted_files) + len(self.unchanged_files),
            "deltaSize": self.delta_size,
            "deltaSizeFormatted": _format_bytes(self.delta_size),
            "compressionRatio": round((1 - self.delta_size / self.total_new_size) * 100, 2) if self.total_new_size > 0 else 0,
        }


def compute_package_diff(base_package: Path, target_package: Path) -> PackageDiff:
    """
    计算两个部署包之间的差异

    Args:
        base_package: 基础包根目录
        target_package: 目标包根目录

    Returns:
        PackageDiff 差异信息
    """
    # 读取包清单
    base_manifest = _read_manifest(base_package)
    target_manifest = _read_manifest(target_package)

    # 扫描文件
    base_files = _scan_package_files(base_package)
    target_files = _scan_package_files(target_package)

    # 计算差异
    added_files = []
    modified_files = []
    deleted_files = []
    unchanged_files = []

    base_paths = set(base_files.keys())
    target_paths = set(target_files.keys())

    # 新增文件
    for path in target_paths - base_paths:
        file_info = target_files[path]
        added_files.append(FileChange(
            path=path,
            change_type="added",
            new_size=file_info["size"],
            new_hash=file_info["hash"],
        ))

    # 删除文件
    for path in base_paths - target_paths:
        file_info = base_files[path]
        deleted_files.append(FileChange(
            path=path,
            change_type="deleted",
            old_size=file_info["size"],
            old_hash=file_info["hash"],
        ))

    # 修改或未变更文件
    for path in base_paths & target_paths:
        base_info = base_files[path]
        target_info = target_files[path]

        if base_info["hash"] != target_info["hash"]:
            # 文件已修改
            modified_files.append(FileChange(
                path=path,
                change_type="modified",
                old_size=base_info["size"],
                new_size=target_info["size"],
                old_hash=base_info["hash"],
                new_hash=target_info["hash"],
            ))
        else:
            # 文件未变更
            unchanged_files.append(FileChange(
                path=path,
                change_type="unchanged",
                old_size=base_info["size"],
                new_size=target_info["size"],
                old_hash=base_info["hash"],
                new_hash=target_info["hash"],
            ))

    # 计算大小
    total_old_size = sum(f["size"] for f in base_files.values())
    total_new_size = sum(f["size"] for f in target_files.values())
    delta_size = sum(f.new_size for f in added_files) + sum(f.new_size for f in modified_files)

    return PackageDiff(
        base_package_id=base_manifest.get("packageId", "unknown"),
        target_package_id=target_manifest.get("packageId", "unknown"),
        added_files=added_files,
        modified_files=modified_files,
        deleted_files=deleted_files,
        unchanged_files=unchanged_files,
        total_old_size=total_old_size,
        total_new_size=total_new_size,
        delta_size=delta_size,
    )


def generate_delta_manifest(diff: PackageDiff, target_manifest: dict) -> dict:
    """
    生成增量包的清单文件

    Args:
        diff: 包差异信息
        target_manifest: 目标包清单

    Returns:
        增量包清单字典
    """
    return {
        "packageId": f"{diff.target_package_id}-delta",
        "deltaPackage": True,
        "basePackageId": diff.base_package_id,
        "targetPackageId": diff.target_package_id,
        "projectKey": target_manifest.get("projectKey"),
        "productVersion": target_manifest.get("productVersion"),
        "sourceEnv": target_manifest.get("sourceEnv"),
        "targetEnv": target_manifest.get("targetEnv"),
        "createdAt": target_manifest.get("createdAt"),
        "changes": diff.change_summary,
        "addedFiles": [f.path for f in diff.added_files],
        "modifiedFiles": [f.path for f in diff.modified_files],
        "deletedFiles": [f.path for f in diff.deleted_files],
    }


def create_delta_package(base_package: Path, target_package: Path, output_dir: Path) -> Path:
    """
    创建增量更新包

    Args:
        base_package: 基础包根目录
        target_package: 目标包根目录
        output_dir: 输出目录

    Returns:
        增量包路径
    """
    # 计算差异
    diff = compute_package_diff(base_package, target_package)

    if not diff.has_changes:
        raise ValueError("No changes detected between packages")

    # 创建增量包目录
    target_manifest = _read_manifest(target_package)
    delta_package_id = f"{diff.target_package_id}-delta"
    delta_package_dir = output_dir / delta_package_id
    delta_package_dir.mkdir(parents=True, exist_ok=True)

    # 生成增量清单
    delta_manifest = generate_delta_manifest(diff, target_manifest)
    (delta_package_dir / "delta-manifest.json").write_text(
        json.dumps(delta_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # 复制新增和修改的文件
    for change in diff.added_files + diff.modified_files:
        source_file = target_package / change.path
        dest_file = delta_package_dir / change.path
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # 复制文件
        import shutil
        shutil.copy2(source_file, dest_file)

    # 生成删除文件列表
    if diff.deleted_files:
        deleted_list = "\n".join(f.path for f in diff.deleted_files)
        (delta_package_dir / "DELETED_FILES.txt").write_text(deleted_list, encoding="utf-8")

    # 生成 README
    readme = _generate_delta_readme(diff, delta_manifest)
    (delta_package_dir / "README.md").write_text(readme, encoding="utf-8")

    # 生成应用脚本
    apply_script = _generate_apply_script(delta_manifest)
    apply_script_path = delta_package_dir / "apply-delta.sh"
    apply_script_path.write_text(apply_script, encoding="utf-8")
    apply_script_path.chmod(0o755)

    return delta_package_dir


def apply_delta_package(base_package: Path, delta_package: Path) -> Path:
    """
    应用增量包到基础包

    Args:
        base_package: 基础包根目录
        delta_package: 增量包根目录

    Returns:
        更新后的包路径
    """
    # 读取增量清单
    delta_manifest = json.loads((delta_package / "delta-manifest.json").read_text(encoding="utf-8"))

    # 验证基础包
    base_manifest = _read_manifest(base_package)
    if base_manifest.get("packageId") != delta_manifest["basePackageId"]:
        raise ValueError(f"Base package mismatch: expected {delta_manifest['basePackageId']}, got {base_manifest.get('packageId')}")

    # 创建输出目录
    output_dir = base_package.parent / delta_manifest["targetPackageId"]
    output_dir.mkdir(parents=True, exist_ok=True)

    # 复制基础包到输出目录
    import shutil
    for item in base_package.iterdir():
        if item.is_file():
            shutil.copy2(item, output_dir / item.name)
        elif item.is_dir():
            shutil.copytree(item, output_dir / item.name, dirs_exist_ok=True)

    # 应用新增和修改的文件
    for file_path in delta_manifest["addedFiles"] + delta_manifest["modifiedFiles"]:
        source_file = delta_package / file_path
        dest_file = output_dir / file_path

        if source_file.exists():
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, dest_file)

    # 删除文件
    for file_path in delta_manifest["deletedFiles"]:
        target_file = output_dir / file_path
        if target_file.exists():
            target_file.unlink()

    # 更新清单
    target_manifest = _read_manifest(delta_package.parent / delta_manifest["targetPackageId"]) if (delta_package.parent / delta_manifest["targetPackageId"]).exists() else delta_manifest
    (output_dir / "manifest.json").write_text(
        json.dumps(target_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return output_dir


# ============================================================================
# 辅助函数
# ============================================================================

def _read_manifest(package_dir: Path) -> dict:
    """读取包清单"""
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _scan_package_files(package_dir: Path, exclude_patterns: list[str] | None = None) -> dict[str, dict]:
    """
    扫描包中的所有文件

    Returns:
        {相对路径: {"size": 字节数, "hash": SHA256}}
    """
    exclude_patterns = exclude_patterns or [
        "manifest.json",  # 清单文件每次都不同
        "package-index.json",  # 索引文件每次都不同
        "*.tar.gz",  # 排除压缩包本身
        "*.parts",  # 排除下载分片
    ]

    files = {}

    for file_path in package_dir.rglob("*"):
        if not file_path.is_file():
            continue

        # 相对路径
        rel_path = str(file_path.relative_to(package_dir))

        # 检查排除模式
        if _should_exclude(rel_path, exclude_patterns):
            continue

        # 计算哈希
        file_hash = _compute_file_hash(file_path)
        file_size = file_path.stat().st_size

        files[rel_path] = {
            "size": file_size,
            "hash": file_hash,
        }

    return files


def _should_exclude(path: str, patterns: list[str]) -> bool:
    """检查文件是否应该被排除"""
    from fnmatch import fnmatch

    for pattern in patterns:
        if fnmatch(path, pattern):
            return True
    return False


def _compute_file_hash(file_path: Path) -> str:
    """计算文件的 SHA256 哈希"""
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _format_bytes(size_bytes: int) -> str:
    """格式化字节大小"""
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.2f} {units[unit_index]}"


def _generate_delta_readme(diff: PackageDiff, manifest: dict) -> str:
    """生成增量包的 README"""
    summary = diff.change_summary

    return f"""# 增量更新包

> 📦 增量包 ID：`{manifest['packageId']}`
> 🔄 基础包：`{diff.base_package_id}`
> 🎯 目标包：`{diff.target_package_id}`

## 变更摘要

- ➕ 新增文件：{summary['added']} 个
- ✏️  修改文件：{summary['modified']} 个
- ➖ 删除文件：{summary['deleted']} 个
- ✅ 未变更文件：{summary['unchanged']} 个

**增量大小**：{summary['deltaSizeFormatted']} （压缩率：{summary['compressionRatio']}%）

## 应用增量更新

### 前提条件

确保你有基础部署包：`{diff.base_package_id}`

### 应用步骤

```bash
# 方法 1：使用自动脚本
./apply-delta.sh /path/to/base-package

# 方法 2：手动应用
cd /path/to/base-package

# 复制新增和修改的文件
cp -r {{delta-package}}/k8s ./
cp -r {{delta-package}}/init ./
# ... 复制其他变更的文件

# 删除文件
cat {{delta-package}}/DELETED_FILES.txt | while read file; do
    rm -f "$file"
done

# 更新清单
cp {{delta-package}}/delta-manifest.json ./manifest.json
```

### 验证

```bash
# 运行质量检查
./quality-gate.sh

# 验证部署
./verify.sh
```

## 变更详情

### 新增文件

"""

    if diff.added_files:
        for change in diff.added_files[:10]:  # 只显示前10个
            readme += f"- `{change.path}` ({_format_bytes(change.new_size)})\n"
        if len(diff.added_files) > 10:
            readme += f"... 还有 {len(diff.added_files) - 10} 个文件\n"
    else:
        readme += "无\n"

    readme += """
### 修改文件

"""

    if diff.modified_files:
        for change in diff.modified_files[:10]:
            old_size = _format_bytes(change.old_size)
            new_size = _format_bytes(change.new_size)
            readme += f"- `{change.path}` ({old_size} → {new_size})\n"
        if len(diff.modified_files) > 10:
            readme += f"... 还有 {len(diff.modified_files) - 10} 个文件\n"
    else:
        readme += "无\n"

    readme += """
### 删除文件

"""

    if diff.deleted_files:
        for change in diff.deleted_files[:10]:
            readme += f"- `{change.path}` ({_format_bytes(change.old_size)})\n"
        if len(diff.deleted_files) > 10:
            readme += f"... 还有 {len(diff.deleted_files) - 10} 个文件\n"
    else:
        readme += "无\n"

    readme += """
## 注意事项

⚠️ **重要**：
1. 应用增量更新前，请备份基础包
2. 确保基础包 ID 匹配
3. 应用后运行质量检查验证完整性
4. 如果增量应用失败，请使用完整包重新部署

---

**生成时间**：{createdAt}
**项目**：{projectKey}
**版本**：{productVersion}
""".format(
        createdAt=manifest.get("createdAt", ""),
        projectKey=manifest.get("projectKey", ""),
        productVersion=manifest.get("productVersion", "")
    )

    return readme


def _generate_apply_script(manifest: dict) -> str:
    """生成增量应用脚本"""
    return f"""#!/bin/bash
# 增量更新应用脚本
# 自动将增量包应用到基础包

set -e

BASE_PACKAGE="$1"
DELTA_PACKAGE="$(cd "$(dirname "$0")" && pwd)"

if [ -z "$BASE_PACKAGE" ]; then
    echo "用法: $0 <基础包路径>"
    exit 1
fi

if [ ! -d "$BASE_PACKAGE" ]; then
    echo "错误：基础包不存在: $BASE_PACKAGE"
    exit 1
fi

echo "应用增量更新..."
echo "基础包: $BASE_PACKAGE"
echo "增量包: $DELTA_PACKAGE"

# 验证基础包 ID
BASE_MANIFEST="$BASE_PACKAGE/manifest.json"
if [ -f "$BASE_MANIFEST" ]; then
    BASE_ID=$(jq -r '.packageId' "$BASE_MANIFEST")
    EXPECTED_BASE_ID="{manifest['basePackageId']}"

    if [ "$BASE_ID" != "$EXPECTED_BASE_ID" ]; then
        echo "错误：基础包 ID 不匹配"
        echo "  期望: $EXPECTED_BASE_ID"
        echo "  实际: $BASE_ID"
        exit 1
    fi
fi

# 备份基础包（可选）
read -p "是否备份基础包？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    BACKUP_PATH="${{BASE_PACKAGE}}.backup-$(date +%Y%m%d-%H%M%S)"
    cp -r "$BASE_PACKAGE" "$BACKUP_PATH"
    echo "备份已保存到: $BACKUP_PATH"
fi

# 应用新增和修改的文件
echo "复制新增和修改的文件..."
ADDED_COUNT={len(manifest.get('addedFiles', []))}
MODIFIED_COUNT={len(manifest.get('modifiedFiles', []))}

cd "$DELTA_PACKAGE"
find . -type f -not -path './delta-manifest.json' -not -path './README.md' -not -path './apply-delta.sh' -not -path './DELETED_FILES.txt' | while read file; do
    rel_path="${{file#./}}"
    dest_file="$BASE_PACKAGE/$rel_path"
    mkdir -p "$(dirname "$dest_file")"
    cp -f "$file" "$dest_file"
    echo "  ✓ $rel_path"
done

# 删除文件
if [ -f "$DELTA_PACKAGE/DELETED_FILES.txt" ]; then
    echo "删除文件..."
    while read file; do
        rm -f "$BASE_PACKAGE/$file"
        echo "  ✗ $file"
    done < "$DELTA_PACKAGE/DELETED_FILES.txt"
fi

# 更新清单
cp -f "$DELTA_PACKAGE/delta-manifest.json" "$BASE_PACKAGE/manifest.json"

echo ""
echo "✅ 增量更新应用完成！"
echo ""
echo "变更摘要:"
echo "  ➕ 新增: $ADDED_COUNT 个文件"
echo "  ✏️  修改: $MODIFIED_COUNT 个文件"
echo "  ➖ 删除: {len(manifest.get('deletedFiles', []))} 个文件"
echo ""
echo "建议运行验证:"
echo "  cd $BASE_PACKAGE"
echo "  ./quality-gate.sh"
"""
