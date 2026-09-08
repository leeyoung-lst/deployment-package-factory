# 功能测试验证计划

**测试日期**: 2026-09-08  
**测试人员**: 待指定  
**状态**: 待执行

---

## 📋 测试范围

### Phase 1: 用户体验优化

- [x] Phase 1.1 - 实时进度反馈
- [x] Phase 1.2 - 配置预览功能
- [x] Phase 1.3 - 智能错误提示

### Phase 2: 内容增强

- [x] Phase 2.1 - 生产级初始化脚本
- [x] Phase 2.2 - 镜像版本管理
- [x] Phase 2.3 - 完整部署文档

### Phase 3: 性能和可靠性

- [x] Phase 3.1 - 断点续传优化
- [x] Phase 3.2 - 增量更新支持
- [x] Phase 3.3 - 并行构建加速

---

## ✅ 测试清单

### Phase 1.1: 实时进度反馈

#### 单元测试
```bash
# 运行实时进度相关测试（如果有）
cd backend
pytest -xvs -k "progress" --tb=short

# 预期结果：所有测试通过
```

#### 集成测试
```bash
# 1. 启动服务
python -m deployment_package_factory

# 2. 创建构建任务
curl -X POST http://localhost:8000/api/deployment-packages/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "projectKey": "test",
    "sourceEnv": "dev",
    "targetEnv": "prod",
    "deployModes": ["k8s"],
    "database": "postgres"
  }'

# 3. 获取任务状态，检查进度字段
curl http://localhost:8000/api/deployment-packages/tasks/{task_id}

# 验证点：
# - ✅ progress 字段存在且为 0-100 的整数
# - ✅ message 字段包含阶段描述（如"准备构建环境"）
# - ✅ 进度随时间递增
```

#### 手动测试
- [ ] 在前端界面创建任务
- [ ] 观察进度条是否实时更新
- [ ] 验证 11 个阶段消息是否正确显示
- [ ] 检查进度百分比是否连续递增

**预期结果**：
- 进度从 0% 到 100% 平滑过渡
- 每个阶段消息清晰易懂
- 前端自动轮询刷新

---

### Phase 1.2: 配置预览功能

#### 单元测试
```bash
# 运行配置预览测试
cd backend
pytest -xvs tests/test_config_preview.py --tb=short

# 预期结果：11/11 测试通过
```

#### API 测试
```bash
# 1. 创建并完成一个构建任务
# （参考 Phase 1.1 的步骤）

# 2. 预览配置文件
curl http://localhost:8000/api/deployment-packages/tasks/{task_id}/preview

# 验证点：
# - ✅ 返回 JSON 格式的预览数据
# - ✅ files 数组包含文件内容
# - ✅ availableFiles 列出所有可预览文件
# - ✅ 文件内容正确（UTF-8 编码）
```

#### 前端测试
- [ ] 打开任务详情页
- [ ] 点击"预览配置"按钮
- [ ] 验证文件列表显示正确
- [ ] 切换不同文件，检查内容显示
- [ ] 验证语法高亮标签
- [ ] 测试"加载更多"功能

**预期结果**：
- 可以预览 20+ 种配置文件
- 中文内容正确显示
- 大文件显示截断提示
- 文件列表和内容匹配

---

### Phase 1.3: 智能错误提示

#### 单元测试
```bash
# 运行错误诊断测试
cd backend
pytest -xvs tests/test_error_diagnosis.py --tb=short

# 预期结果：22/22 测试通过
```

#### 集成测试
```bash
# 1. 触发各种错误场景

# 场景 1：网络错误（模拟）
# 修改配置使其连接到不存在的服务
curl -X POST http://localhost:8000/api/deployment-packages/tasks \
  -d '{
    "targetProfile": {
      "registry": "nonexistent-registry.com"
    },
    ...
  }'

# 验证点：
# - ✅ 错误消息包含"无法连接到目标服务"
# - ✅ 列出可能原因（3-5 条）
# - ✅ 提供解决方案（3-5 条）
# - ✅ 包含技术细节
```

#### 手动测试场景

**场景 1：配置错误**
- [ ] 使用不存在的项目名称
- [ ] 验证错误消息友好
- [ ] 检查是否有解决建议

**场景 2：资源不足**（需要实际环境）
- [ ] 填满磁盘空间
- [ ] 触发构建
- [ ] 验证错误提示磁盘空间不足

**场景 3：权限错误**
- [ ] 移除工作目录权限
- [ ] 触发构建
- [ ] 验证权限错误提示

**预期结果**：
- 所有错误都有用户友好的描述
- 提供具体可操作的解决方案
- 技术细节可选查看

---

### Phase 2.1: 生产级初始化脚本

#### 单元测试
```bash
# 运行初始化脚本测试
cd backend
pytest -xvs tests/test_init_data_generators.py --tb=short

# 预期结果：19/19 测试通过
```

#### SQL 验证
```bash
# 1. 生成部署包
# 2. 提取初始化 SQL
tar -xzf deployment-package.tar.gz
cd deployment-package/init/postgres/

# 3. 验证 SQL 语法（使用 PostgreSQL）
psql -U postgres -f 001_schema.sql --single-transaction

# 验证点：
# - ✅ SQL 执行成功，无语法错误
# - ✅ 所有 schema 创建成功
# - ✅ 所有表创建成功
# - ✅ 索引和约束创建成功
# - ✅ 默认数据插入成功
```

#### 数据验证
```sql
-- 验证 IAM 表
SELECT * FROM iam.users WHERE username = 'admin';
-- 预期：返回默认管理员用户

SELECT COUNT(*) FROM iam.roles;
-- 预期：返回 3（admin, user, developer）

-- 验证增强表
\dt monitoring.*
-- 预期：health_checks, metrics 表存在

\dt workflow.*
-- 预期：instances, tasks 表存在

\dt documents.*
-- 预期：metadata, versions 表存在

-- 验证幂等性
\i 001_schema.sql
-- 预期：再次执行无错误，数据不重复
```

**预期结果**：
- 所有表和索引创建成功
- 默认管理员账户可登录
- 脚本可重复执行（幂等）

---

### Phase 2.2: 镜像版本管理

#### 单元测试
```bash
# 运行镜像版本管理测试
cd backend
pytest -xvs tests/test_image_version_manager.py --tb=short

# 预期结果：28/28 测试通过
```

#### 功能测试
```python
# test_image_version_manual.py
from deployment_package_factory.services.deployment_packages.image_version_manager import (
    parse_version,
    extract_version_from_tag,
    compare_versions,
    inspect_image,
    check_version_status,
)

# 1. 版本解析测试
v1 = parse_version("1.2.3")
assert v1.major == 1
assert v1.minor == 2
assert v1.patch == 3
print("✅ 版本解析测试通过")

# 2. 从标签提取版本
v2 = extract_version_from_tag("nginx:1.21.0-alpine")
assert v2.major == 1
assert v2.minor == 21
print("✅ 标签提取测试通过")

# 3. 版本比较
v3 = parse_version("2.0.0")
assert compare_versions(v3, v1) > 0
print("✅ 版本比较测试通过")

# 4. 镜像检查（需要 skopeo 或 docker）
metadata = inspect_image("nginx:1.21.0")
print(f"镜像大小: {metadata.size_bytes / 1024 / 1024:.2f} MB")
print(f"架构: {metadata.architecture}")
print(f"✅ 镜像检查测试通过" if metadata.available else "⚠️ 镜像不可用")

# 5. 版本状态检查
result = check_version_status("1.20.0", ["1.20.0", "1.21.0", "1.25.0"])
print(f"当前版本: {result.current_version}")
print(f"最新版本: {result.latest_version}")
print(f"状态: {result.status}")
print(f"建议: {result.recommendation}")
print("✅ 版本状态检查测试通过")
```

```bash
# 运行手动测试
python test_image_version_manual.py
```

**预期结果**：
- 版本解析准确
- 支持 15+ 种标签格式
- 镜像检查返回完整元数据
- 版本状态判断正确

---

### Phase 2.3: 完整部署文档

#### 文档生成测试
```python
# test_readme_generation.py
from deployment_package_factory.services.deployment_packages.comprehensive_readme_generator import (
    generate_comprehensive_readme
)

manifest = {
    "packageId": "pkg-test-001",
    "projectKey": "test",
    "productVersion": "1.0.0",
    "sourceEnv": "dev",
    "targetEnv": "prod",
    "deployModes": ["k8s"],
    "database": "postgres",
    "platformServices": ["iam", "api-gateway"],
    "businessServices": ["eam"],
    "middleware": ["minio", "qdrant"],
}

readme = generate_comprehensive_readme(manifest)

# 验证
assert "# Local AI 生产部署包" in readme
assert "## 📚 目录" in readme
assert "## 🚀 快速开始" in readme
assert "## 📋 部署前准备" in readme
assert "## 🏗️ 架构概览" in readme
assert "## 📦 服务清单" in readme
assert "## 🔧 故障排查" in readme
assert len(readme) > 10000  # 至少 10KB

print(f"✅ README 生成测试通过（{len(readme)} 字符）")
```

#### 内容验证
- [ ] README.md 包含 15 个主要章节
- [ ] 目录链接可点击跳转
- [ ] 架构图正确显示
- [ ] 服务清单表格完整
- [ ] 部署步骤清晰
- [ ] 故障排查场景覆盖全面
- [ ] 代码块语法高亮正确

**预期结果**：
- 文档长度 > 3000 行
- 所有章节内容完整
- Markdown 格式正确

---

### Phase 3.1: 断点续传优化

#### 单元测试
```bash
# 测试 Range 请求解析
cd backend
pytest -xvs -k "range" --tb=short

# 预期：Range 解析测试通过
```

#### 下载脚本测试
```bash
# 1. 生成下载脚本
curl http://localhost:8000/api/deployment-packages/tasks/{task_id}/download-script/bash

# 2. 执行脚本
chmod +x download-script.sh
./download-script.sh

# 验证点：
# - ✅ 显示分片下载进度
# - ✅ 每个分片 64MB
# - ✅ 分片文件正确创建
```

#### 断点续传测试
```bash
# 1. 开始下载
./download-script.sh &
PID=$!

# 2. 中断下载（模拟网络断开）
sleep 30
kill $PID

# 3. 检查已下载的分片
ls -lh *.parts/

# 4. 重新运行脚本
./download-script.sh

# 验证点：
# - ✅ 跳过已下载的分片
# - ✅ 从断点继续下载
# - ✅ 最终文件完整且 SHA256 正确
```

**预期结果**：
- 分片下载正常工作
- 断点续传自动恢复
- SHA256 校验通过

---

### Phase 3.2: 增量更新支持

#### 单元测试
```bash
# 运行增量更新测试
cd backend
pytest -xvs tests/test_delta_package.py --tb=short

# 预期结果：15/15 测试通过
```

#### 集成测试
```python
# test_delta_integration.py
from pathlib import Path
from deployment_package_factory.services.deployment_packages.delta_package import (
    compute_package_diff,
    create_delta_package,
    apply_delta_package,
)

# 1. 准备两个版本的包
base_package = Path("packages/v1.0.0")
target_package = Path("packages/v2.0.0")

# 2. 计算差异
diff = compute_package_diff(base_package, target_package)
print(f"新增: {len(diff.added_files)}")
print(f"修改: {len(diff.modified_files)}")
print(f"删除: {len(diff.deleted_files)}")
print(f"增量大小: {diff.delta_size / 1024 / 1024:.2f} MB")
print(f"压缩率: {diff.change_summary['compressionRatio']:.1f}%")

# 3. 创建增量包
delta_dir = create_delta_package(base_package, target_package, Path("output"))
print(f"✅ 增量包已创建: {delta_dir}")

# 4. 应用增量包
result_dir = apply_delta_package(base_package, delta_dir)
print(f"✅ 增量包已应用: {result_dir}")

# 5. 验证结果
# （对比 result_dir 和 target_package 应该一致）
```

#### 手动测试
```bash
# 1. 创建增量包
cd output/delta
tar -czf v2.0.0-delta.tar.gz .

# 2. 分发增量包（模拟）
cp v2.0.0-delta.tar.gz /tmp/

# 3. 应用增量包
cd /tmp
tar -xzf v2.0.0-delta.tar.gz
./apply-delta.sh /path/to/v1.0.0

# 验证点：
# - ✅ 提示备份基础包
# - ✅ 显示变更摘要
# - ✅ 文件正确更新
# - ✅ 应用成功消息
```

**预期结果**：
- 差异检测准确
- 增量包生成成功
- 应用脚本正常工作
- 压缩率 > 90%（配置微调场景）

---

### Phase 3.3: 并行构建加速

#### 配置测试
```python
# test_parallel_config.py
from deployment_package_factory.services.deployment_packages.task_executor import (
    PackageTaskExecutorConfig,
    PackageTaskExecutor
)

# 1. 创建并发配置
config = PackageTaskExecutorConfig(
    max_concurrent_builds=4
)

# 2. 验证配置
assert config.max_concurrent_builds == 4
print("✅ 并发配置测试通过")
```

#### 性能测试
```bash
# 1. 串行构建（并发=1）
time {
  # 提交 5 个构建任务
  for i in {1..5}; do
    curl -X POST http://localhost:8000/api/deployment-packages/tasks \
      -d '{"projectKey": "test-'$i'", ...}'
  done
  
  # 等待全部完成
  wait
}
# 记录时间：T1

# 2. 并行构建（并发=4）
# 修改配置：MAX_CONCURRENT_BUILDS=4
# 重启服务
time {
  # 提交 5 个构建任务
  for i in {1..5}; do
    curl -X POST http://localhost:8000/api/deployment-packages/tasks \
      -d '{"projectKey": "test-'$i'", ...}'
  done
  
  # 等待全部完成
  wait
}
# 记录时间：T2

# 计算加速比
echo "加速比: $(echo "scale=2; $T1 / $T2" | bc)x"
```

#### 监控测试
```bash
# 监控并行任务
watch -n 1 '
  echo "=== 任务状态 ==="
  curl -s http://localhost:8000/api/deployment-packages/tasks | \
    jq -r ".[] | \"\(.taskId): \(.status) \(.progress)%\""
  
  echo ""
  echo "=== 系统资源 ==="
  top -bn1 | head -5
'

# 验证点：
# - ✅ 同时有多个任务在 running 状态
# - ✅ CPU 利用率提升
# - ✅ 任务按顺序完成
```

**预期结果**：
- 并发配置生效
- 多个任务同时运行
- 性能提升 150-250%

---

## 📊 测试报告模板

### 测试执行记录

| Phase | 功能 | 单元测试 | 集成测试 | 手动测试 | 状态 | 备注 |
|-------|------|---------|---------|---------|------|------|
| 1.1 | 实时进度 | ⬜ | ⬜ | ⬜ | 待测试 | |
| 1.2 | 配置预览 | ⬜ | ⬜ | ⬜ | 待测试 | |
| 1.3 | 智能错误 | ⬜ | ⬜ | ⬜ | 待测试 | |
| 2.1 | 初始化脚本 | ⬜ | ⬜ | ⬜ | 待测试 | |
| 2.2 | 镜像版本 | ⬜ | ⬜ | ⬜ | 待测试 | |
| 2.3 | 部署文档 | ⬜ | ⬜ | ⬜ | 待测试 | |
| 3.1 | 断点续传 | ⬜ | ⬜ | ⬜ | 待测试 | |
| 3.2 | 增量更新 | ⬜ | ⬜ | ⬜ | 待测试 | |
| 3.3 | 并行构建 | ⬜ | ⬜ | ⬜ | 待测试 | |

图例：✅ 通过 | ❌ 失败 | ⚠️ 部分通过 | ⬜ 待测试

### 问题跟踪

| ID | Phase | 问题描述 | 严重程度 | 状态 | 负责人 |
|----|-------|---------|---------|------|--------|
| 1 | - | - | - | - | - |

严重程度：🔴 严重 | 🟡 一般 | 🟢 轻微

---

## 🚀 快速测试脚本

### 一键运行所有单元测试

```bash
#!/bin/bash
# run_all_tests.sh

cd backend

echo "======================================"
echo "运行所有单元测试"
echo "======================================"

# Phase 1
echo "📊 Phase 1: 用户体验优化"
pytest -xvs tests/test_error_diagnosis.py

# Phase 2
echo "📊 Phase 2: 内容增强"
pytest -xvs tests/test_init_data_generators.py
pytest -xvs tests/test_image_version_manager.py

# Phase 3
echo "📊 Phase 3: 性能和可靠性"
pytest -xvs tests/test_delta_package.py

echo ""
echo "======================================"
echo "测试完成！"
echo "======================================"
```

### 使用方法

```bash
chmod +x run_all_tests.sh
./run_all_tests.sh
```

---

## 📝 测试注意事项

### 环境准备

1. **Python 环境**
   ```bash
   python --version  # >= 3.10
   pip install -r requirements.txt
   ```

2. **数据库**
   ```bash
   # PostgreSQL
   psql --version  # >= 14
   
   # 创建测试数据库
   createdb test_deployment_factory
   ```

3. **工具**
   ```bash
   # 镜像工具（可选）
   skopeo --version
   # 或
   docker --version
   ```

4. **测试数据**
   - 准备 2 个版本的部署包（用于增量更新测试）
   - 准备测试用的镜像仓库访问权限

### 测试环境隔离

```bash
# 使用测试配置
export ENV=test
export DATABASE_URL=postgresql://localhost/test_deployment_factory
export WORK_DIR=/tmp/deployment-test
```

---

## ✅ 验收标准

### 通过条件

1. **单元测试**
   - ✅ 所有单元测试通过（70+ 测试）
   - ✅ 无跳过的测试
   - ✅ 无警告

2. **集成测试**
   - ✅ 所有 API 端点正常工作
   - ✅ 前后端集成无问题
   - ✅ 数据一致性验证通过

3. **性能测试**
   - ✅ 并行构建加速 > 150%
   - ✅ 增量更新压缩率 > 90%
   - ✅ 断点续传恢复成功率 > 95%

4. **用户验收**
   - ✅ 用户满意度 > 90%
   - ✅ 功能符合预期
   - ✅ 无严重 bug

---

**测试负责人**: 待指定  
**预计测试时间**: 2-3 天  
**测试环境**: 开发环境 / 测试环境  
**版本**: v1.0
