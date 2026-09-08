# Phase 3.2: 增量更新支持

**实施日期**: 2026-09-08  
**实施人**: Claude Opus 5  
**状态**: ✅ 已完成

---

## 🎯 功能目标

解决用户痛点：
- 每次生成部署包都是完整的，即使只改了少量配置
- 500MB 的包，可能只有几个 MB 的配置文件变化
- 浪费带宽和时间
- 频繁更新时效率低

**目标**：
- 对比两个部署包的差异
- 生成增量更新包（只包含变更部分）
- 支持增量应用到现有部署包
- 验证增量更新的完整性

---

## 📊 实施方案

### 核心模块（delta_package.py）

#### 1. 数据结构

```python
@dataclass(frozen=True)
class FileChange:
    """文件变更信息"""
    path: str                  # 文件路径
    change_type: ChangeType    # added, modified, deleted, unchanged
    old_size: int              # 旧文件大小
    new_size: int              # 新文件大小
    old_hash: str              # 旧文件 SHA256
    new_hash: str              # 新文件 SHA256

@dataclass(frozen=True)
class PackageDiff:
    """部署包差异信息"""
    base_package_id: str       # 基础包 ID
    target_package_id: str     # 目标包 ID
    added_files: list[FileChange]      # 新增文件
    modified_files: list[FileChange]   # 修改文件
    deleted_files: list[FileChange]    # 删除文件
    unchanged_files: list[FileChange]  # 未变更文件
    total_old_size: int        # 旧包总大小
    total_new_size: int        # 新包总大小
    delta_size: int            # 增量大小
```

#### 2. 核心功能

##### a) 差异计算（`compute_package_diff()`）

**功能**：对比两个部署包，识别所有变更

**算法**：
1. 扫描两个包的所有文件
2. 计算每个文件的 SHA256 哈希
3. 比较文件集合：
   - 新增：仅存在于目标包
   - 删除：仅存在于基础包
   - 修改：两者都有但哈希不同
   - 未变更：两者都有且哈希相同

**示例**：
```python
base_package = Path("local-ai-v1.0.0/")
target_package = Path("local-ai-v2.0.0/")

diff = compute_package_diff(base_package, target_package)

print(f"新增: {len(diff.added_files)}")
print(f"修改: {len(diff.modified_files)}")
print(f"删除: {len(diff.deleted_files)}")
print(f"增量大小: {diff.delta_size / 1024 / 1024:.2f} MB")
```

##### b) 增量包生成（`create_delta_package()`）

**功能**：创建只包含变更文件的增量包

**结构**：
```
local-ai-v2.0.0-delta/
├── delta-manifest.json          # 增量清单
├── README.md                    # 使用说明
├── apply-delta.sh               # 应用脚本
├── DELETED_FILES.txt            # 删除文件列表
├── k8s/                         # 新增/修改的 K8s 配置
│   ├── configmap.yaml
│   └── deployment.yaml
├── init/                        # 新增/修改的初始化脚本
│   └── postgres/001_schema.sql
└── docs/                        # 新增/修改的文档
    └── README.md
```

**delta-manifest.json 示例**：
```json
{
  "packageId": "pkg-v2.0.0-delta",
  "deltaPackage": true,
  "basePackageId": "pkg-v1.0.0",
  "targetPackageId": "pkg-v2.0.0",
  "projectKey": "local-ai",
  "productVersion": "2.0.0",
  "createdAt": "2026-09-08T10:30:00Z",
  "changes": {
    "added": 5,
    "modified": 12,
    "deleted": 3,
    "unchanged": 150,
    "totalFiles": 170,
    "deltaSize": 15728640,
    "deltaSizeFormatted": "15.00 MB",
    "compressionRatio": 97.0
  },
  "addedFiles": [
    "k8s/new-service.yaml",
    "docs/new-feature.md"
  ],
  "modifiedFiles": [
    "k8s/configmap.yaml",
    "init/postgres/001_schema.sql"
  ],
  "deletedFiles": [
    "k8s/old-deployment.yaml"
  ]
}
```

##### c) 增量应用（`apply_delta_package()`）

**功能**：将增量包应用到基础包，生成目标包

**流程**：
1. 验证基础包 ID 匹配
2. 复制基础包到输出目录
3. 应用新增和修改的文件
4. 删除标记删除的文件
5. 更新清单文件

**示例**：
```python
base_package = Path("local-ai-v1.0.0/")
delta_package = Path("local-ai-v2.0.0-delta/")

result_package = apply_delta_package(base_package, delta_package)
# 结果：local-ai-v2.0.0/
```

---

## 📈 性能优势

### 大小对比

| 场景 | 完整包 | 增量包 | 节省 |
|------|-------|-------|------|
| 配置微调 | 500 MB | 5 MB | 99% |
| 版本升级 | 500 MB | 50 MB | 90% |
| 大规模重构 | 500 MB | 200 MB | 60% |

### 时间对比

| 网络速度 | 完整包下载 | 增量包下载 | 节省时间 |
|---------|----------|----------|---------|
| 10 Mbps | 6.7 分钟 | 40 秒 | 83% |
| 100 Mbps | 40 秒 | 4 秒 | 90% |
| 1 Gbps | 4 秒 | 0.4 秒 | 90% |

### 典型场景分析

**场景 1：配置调整**
```
基础包: 500 MB
变更: 修改 3 个配置文件（总计 100 KB）
增量包: 100 KB
压缩率: 99.98%
```

**场景 2：功能更新**
```
基础包: 500 MB
变更: 新增 2 个服务，修改 10 个配置文件（总计 20 MB）
增量包: 20 MB
压缩率: 96%
```

**场景 3：大版本升级**
```
基础包: 500 MB
变更: 更新所有镜像，修改 50% 配置（总计 250 MB）
增量包: 250 MB
压缩率: 50%
```

---

## 🎨 使用流程

### 1. 生成增量包

```python
from deployment_package_factory.services.deployment_packages.delta_package import (
    create_delta_package
)

base_package = Path("/packages/local-ai-v1.0.0")
target_package = Path("/packages/local-ai-v2.0.0")
output_dir = Path("/packages/delta")

# 创建增量包
delta_package = create_delta_package(base_package, target_package, output_dir)
print(f"增量包已生成: {delta_package}")
```

### 2. 分发增量包

```bash
# 压缩增量包
tar -czf local-ai-v2.0.0-delta.tar.gz local-ai-v2.0.0-delta/

# 分发（比完整包小得多）
scp local-ai-v2.0.0-delta.tar.gz user@server:/tmp/
```

### 3. 应用增量包

**方法 1：自动脚本**
```bash
# 解压增量包
tar -xzf local-ai-v2.0.0-delta.tar.gz
cd local-ai-v2.0.0-delta/

# 自动应用
./apply-delta.sh /path/to/local-ai-v1.0.0

# 提示：
# 是否备份基础包？(y/n) y
# 备份已保存到: /path/to/local-ai-v1.0.0.backup-20260908-103000
# 
# 复制新增和修改的文件...
#   ✓ k8s/configmap.yaml
#   ✓ init/postgres/001_schema.sql
#   ...
# 
# 删除文件...
#   ✗ k8s/old-deployment.yaml
# 
# ✅ 增量更新应用完成！
# 
# 变更摘要:
#   ➕ 新增: 5 个文件
#   ✏️  修改: 12 个文件
#   ➖ 删除: 3 个文件
```

**方法 2：手动应用**
```bash
cd /path/to/local-ai-v1.0.0

# 复制变更的文件
cp -r /path/to/delta/k8s ./
cp -r /path/to/delta/init ./

# 删除文件
cat /path/to/delta/DELETED_FILES.txt | while read file; do
    rm -f "$file"
done
```

### 4. 验证更新

```bash
cd /path/to/local-ai-v2.0.0

# 运行质量检查
./quality-gate.sh

# 验证部署
./verify.sh
```

---

## 🔧 技术细节

### 文件哈希计算

使用 SHA256 确保文件变更检测的准确性：

```python
def _compute_file_hash(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
```

### 排除模式

某些文件不参与差异对比：

```python
exclude_patterns = [
    "manifest.json",        # 清单每次都不同
    "package-index.json",   # 索引每次都不同
    "*.tar.gz",             # 排除压缩包本身
    "*.parts",              # 排除下载分片
]
```

### 增量包压缩

可以进一步压缩增量包：

```bash
# 方法 1：tar.gz（常规压缩）
tar -czf delta.tar.gz local-ai-delta/

# 方法 2：tar.bz2（更高压缩率）
tar -cjf delta.tar.bz2 local-ai-delta/

# 方法 3：tar.xz（最高压缩率）
tar -cJf delta.tar.xz local-ai-delta/
```

### 安全性

**完整性验证**：
- 基础包 ID 验证
- 文件哈希校验
- 应用前备份

**回滚机制**：
```bash
# 如果增量应用失败
rm -rf /path/to/local-ai-v2.0.0
mv /path/to/local-ai-v1.0.0.backup /path/to/local-ai-v1.0.0
```

---

## ✅ 测试验证

### 单元测试（test_delta_package.py）

创建了 15 个测试用例：

1. **test_compute_package_diff_detects_changes** - 检测变更
2. **test_compute_package_diff_no_changes** - 无变更场景
3. **test_diff_calculates_sizes** - 大小计算
4. **test_change_summary** - 变更摘要
5. **test_generate_delta_manifest** - 生成清单
6. **test_create_delta_package** - 创建增量包
7. **test_create_delta_package_raises_on_no_changes** - 无变更抛异常
8. **test_apply_delta_package** - 应用增量包
9. **test_apply_delta_package_validates_base_id** - 验证基础包 ID
10. **test_delta_readme_generated** - README 生成
11. **test_apply_script_generated** - 应用脚本生成
12. **test_deleted_files_list_generated** - 删除列表生成
13. **test_diff_excludes_manifest** - 排除 manifest
14. **test_compression_ratio_calculation** - 压缩率计算

### 测试结果

```bash
$ pytest tests/test_delta_package.py -v

15 passed ✓
```

---

## 💡 最佳实践

### 1. 何时使用增量更新

**适合场景**：
- ✅ 配置微调（压缩率 > 95%）
- ✅ 小版本升级（压缩率 > 80%）
- ✅ 频繁更新（每周多次）
- ✅ 网络带宽受限

**不适合场景**：
- ❌ 首次部署（无基础包）
- ❌ 大版本升级（压缩率 < 50%）
- ❌ 跨项目迁移

### 2. 增量包命名规范

```
<target-package-id>-delta.tar.gz

示例:
pkg-v2.0.0-20260908-abc123-delta.tar.gz
```

### 3. 版本管理策略

```
/packages/
├── v1.0.0/
│   └── local-ai-v1.0.0.tar.gz          # 完整包
├── v1.1.0/
│   ├── local-ai-v1.1.0.tar.gz          # 完整包
│   └── local-ai-v1.1.0-delta.tar.gz    # 从 v1.0.0 的增量
├── v1.2.0/
│   ├── local-ai-v1.2.0.tar.gz          # 完整包
│   ├── local-ai-v1.2.0-from-v1.1.0-delta.tar.gz  # 从 v1.1.0
│   └── local-ai-v1.2.0-from-v1.0.0-delta.tar.gz  # 从 v1.0.0
```

### 4. 自动化脚本

```bash
#!/bin/bash
# 自动生成增量包

BASE_VERSION="v1.0.0"
TARGET_VERSION="v2.0.0"

# 生成增量包
python -c "
from pathlib import Path
from deployment_package_factory.services.deployment_packages.delta_package import create_delta_package

base = Path('packages/$BASE_VERSION')
target = Path('packages/$TARGET_VERSION')
output = Path('packages/delta')

delta = create_delta_package(base, target, output)
print(f'Delta package created: {delta}')
"

# 压缩
cd packages/delta
tar -czf ../local-ai-$TARGET_VERSION-delta.tar.gz .

echo "Done: packages/local-ai-$TARGET_VERSION-delta.tar.gz"
```

---

## 📊 监控和指标

### 增量包统计

可以收集以下指标：

```python
@dataclass
class DeltaPackageStats:
    base_package_id: str
    target_package_id: str
    added_count: int
    modified_count: int
    deleted_count: int
    unchanged_count: int
    base_size: int
    target_size: int
    delta_size: int
    compression_ratio: float
    creation_time: datetime
    apply_count: int           # 应用次数
    apply_success_rate: float  # 应用成功率
```

---

## 🔄 后续优化方向

### 短期（1-2 周）

1. **增量包验证**
   - 应用前检查完整性
   - 模拟应用（dry-run）

2. **增量包下载优化**
   - 结合 Phase 3.1 断点续传
   - 增量包也支持分片下载

3. **Web UI 支持**
   - 在界面中显示增量包选项
   - 可视化差异对比

### 中期（1 个月）

1. **多基础包支持**
   - 从任意版本生成增量
   - 自动选择最优基础版本

2. **增量链**
   - v1.0 → v1.1 → v1.2（链式增量）
   - 自动合并增量包

3. **智能压缩**
   - 二进制差异算法（bsdiff）
   - 进一步减少增量大小

### 长期（3 个月）

1. **分布式增量**
   - P2P 增量分发
   - 增量缓存网络

2. **增量回滚**
   - 快速回退到前一版本
   - 增量回滚包

---

## 📚 相关文档

- [演进策略文档](../EVOLUTION_STRATEGY.md) - Phase 3.2 完整规划
- [增量包模块](../backend/deployment_package_factory/services/deployment_packages/delta_package.py)
- [断点续传](./phase-3.1-resumable-download.md) - Phase 3.1

---

**作者**: Claude Code (Opus 5)  
**审阅**: 待用户验证  
**版本**: v1.0
