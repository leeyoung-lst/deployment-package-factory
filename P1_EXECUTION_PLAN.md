# P1 阶段执行计划 - builder.py 模块化重构

**开始时间**：2026-09-07  
**目标**：builder.py 从 1,322 行降至 ~900 行  
**预估时间**：1-2 周  

---

## 📊 当前状态分析

### builder.py 基本信息
- **当前行数**：1,322 行
- **目标行数**：~900 行
- **需要减少**：~420 行（32%）
- **函数总数**：66 个
- **类定义**：1 个（RuntimeSourceImage）

### 功能模块分析

#### 1. 配置管理相关（~200 行）
**函数列表**：
- `_apply_project_build_defaults()` - 应用项目默认配置
- `_resolve_runtime_env()` - 解析运行时环境变量
- `_resolve_env_value()` - 解析环境变量值
- `_runtime_secret_names()` - 运行时密钥名称
- `_runtime_secret_keys()` - 运行时密钥键名
- `_source_list()` - 源列表解析
- `_middleware_config()` - 中间件配置
- 常量：`DEFAULT_RUNTIME_SECRET_NAMES`、`RUNTIME_SECRET_NAME_ALIASES`、`RUNTIME_SECRET_KEY_ALIASES`

**提取目标**：config_manager.py

#### 2. 文件渲染相关（~150 行）
**函数列表**：
- `_readme()` - README 生成
- `_images_txt()` - 镜像清单
- `_pull_images_script()` - 拉取脚本
- `_save_images_script()` - 保存脚本
- `_load_images_script()` - 加载脚本
- `_validation_summary()` - 验证摘要
- `_package_index()` - 包索引
- `_file_index_entry()` - 文件索引条目
- `_section()` / `_section_prefix()` - 索引分组

**提取目标**：file_content_generator.py

#### 3. 镜像相关辅助函数（~100 行）
**函数列表**：
- `_image_path_without_tag()` - 去除标签
- `_with_default_tag()` - 添加默认标签
- `_target_image_ref()` - 目标镜像引用
- `_has_registry()` - 是否包含仓库
- `_safe_image_filename()` - 安全文件名
- `_split_image_tag()` - 分割镜像标签
- `_matches_catalog_image()` - 匹配目录镜像
- `_image_registry_priority()` - 仓库优先级
- `_normalize_image_id()` - 规范化镜像 ID
- `_source_image_ref()` / `_source_export_ref()` / `_runtime_source_ref()` - 各种镜像引用

**提取目标**：image_utils.py

#### 4. 文件系统工具（~50 行）
**函数列表**：
- `_write_text()` - 写文本文件
- `_write_script()` - 写脚本文件
- `_tar_metadata_filter()` - tar 元数据过滤
- `_sha256s()` - 批量 SHA256
- `_file_sha256()` - 单文件 SHA256
- `_archive_lock()` - 归档锁

**提取目标**：filesystem_utils.py

#### 5. 保留在 builder.py 的核心逻辑（~822 行）
- `build_deployment_package()` - 主构建函数
- `check_image_export_environment()` - 环境检查
- `_manifest()` - 清单生成
- `_public_manifest()` - 公开清单
- `_image_entries()` - 镜像条目
- `_discover_runtime_source_images()` - 发现运行时镜像
- `_discover_runtime_business_images()` - 发现业务镜像
- `_preview_with_*()` - 预览增强
- `_registered_microservices_for_request()` - 微服务查询
- `_export_image_archives()` - 镜像导出核心
- 所有 Kubernetes 相关函数
- 所有镜像导出执行函数

---

## 🎯 重构策略

### Phase 1：提取工具函数模块（3-4 天）

#### Step 1.1：创建 image_utils.py
- 提取所有镜像路径/标签处理函数
- 添加单元测试
- 更新 builder.py 导入

#### Step 1.2：创建 filesystem_utils.py
- 提取文件写入和哈希计算函数
- 添加单元测试
- 更新 builder.py 导入

#### Step 1.3：验证测试
- 运行完整测试套件
- 确保 193/193 通过

### Phase 2：提取内容生成模块（3-4 天）

#### Step 2.1：创建 file_content_generator.py
- 提取 README、镜像清单、脚本生成函数
- 提取包索引生成函数
- 添加单元测试
- 更新 builder.py 导入

#### Step 2.2：验证测试
- 运行完整测试套件
- 确保所有测试通过

### Phase 3：提取配置管理模块（4-5 天）

#### Step 3.1：创建 config_manager.py
- 提取环境变量解析函数
- 提取密钥配置函数
- 提取项目默认配置函数
- 移动相关常量
- 添加单元测试

#### Step 3.2：更新 builder.py
- 导入新模块
- 简化主流程

#### Step 3.3：验证测试
- 运行完整测试套件
- 确保所有测试通过

### Phase 4：文档和总结（1-2 天）

#### Step 4.1：更新文档
- 更新模块 README
- 更新架构图
- 记录重构决策

#### Step 4.2：性能验证
- 运行端到端测试
- 对比重构前后性能

#### Step 4.3：提交和推送
- 分批提交（每个新模块一次）
- 推送到远程仓库

---

## 📋 详细任务清单

### Phase 1：工具函数模块 ✅

#### Task 1.1：创建 image_utils.py
- [ ] 创建文件骨架
- [ ] 提取镜像路径处理函数（10 个）
- [ ] 添加类型注解
- [ ] 编写单元测试
- [ ] 更新 builder.py 导入

#### Task 1.2：创建 filesystem_utils.py
- [ ] 创建文件骨架
- [ ] 提取文件操作函数（6 个）
- [ ] 添加类型注解
- [ ] 编写单元测试
- [ ] 更新 builder.py 导入

#### Task 1.3：验证 Phase 1
- [ ] 运行测试套件
- [ ] 检查代码覆盖率
- [ ] 提交 Phase 1 变更

**预估产出**：
- 新增 2 个模块文件（~200 行）
- 新增 2 个测试文件（~150 行）
- builder.py 减少 ~150 行
- builder.py 当前行数：~1,172 行

---

### Phase 2：内容生成模块 ✅

#### Task 2.1：创建 file_content_generator.py
- [ ] 创建文件骨架
- [ ] 提取 README 生成函数
- [ ] 提取镜像清单生成函数
- [ ] 提取脚本生成函数（pull/save/load）
- [ ] 提取包索引生成函数
- [ ] 添加类型注解
- [ ] 编写单元测试

#### Task 2.2：更新 builder.py
- [ ] 导入新模块
- [ ] 替换函数调用
- [ ] 清理未使用代码

#### Task 2.3：验证 Phase 2
- [ ] 运行测试套件
- [ ] 检查代码覆盖率
- [ ] 提交 Phase 2 变更

**预估产出**：
- 新增 1 个模块文件（~180 行）
- 新增 1 个测试文件（~120 行）
- builder.py 减少 ~150 行
- builder.py 当前行数：~1,022 行

---

### Phase 3：配置管理模块 ✅

#### Task 3.1：创建 config_manager.py
- [ ] 创建文件骨架
- [ ] 移动配置常量（3 个）
- [ ] 提取环境变量解析函数（3 个）
- [ ] 提取密钥配置函数（2 个）
- [ ] 提取项目配置函数（2 个）
- [ ] 添加类型注解
- [ ] 编写单元测试

#### Task 3.2：更新 builder.py
- [ ] 导入新模块
- [ ] 替换函数调用
- [ ] 清理未使用代码

#### Task 3.3：验证 Phase 3
- [ ] 运行测试套件
- [ ] 检查代码覆盖率
- [ ] 提交 Phase 3 变更

**预估产出**：
- 新增 1 个模块文件（~220 行）
- 新增 1 个测试文件（~150 行）
- builder.py 减少 ~200 行
- builder.py 当前行数：~822 行

---

### Phase 4：文档和验收 ✅

#### Task 4.1：更新文档
- [ ] 更新模块 README
- [ ] 创建架构图
- [ ] 编写重构总结

#### Task 4.2：性能验证
- [ ] 端到端测试
- [ ] 性能对比
- [ ] 内存占用分析

#### Task 4.3：最终提交
- [ ] 提交文档更新
- [ ] 推送到远程仓库
- [ ] 创建 P1 完成报告

---

## 📊 预期成果

### 代码指标

| 指标 | 当前 | 目标 | 改进 |
|------|------|------|------|
| builder.py 行数 | 1,322 | ~822 | -500 行 (38%) |
| 新增模块 | 0 | 4 | +4 个 |
| 新增测试 | 0 | 4 | +4 个文件 |
| 函数职责 | 混杂 | 单一 | ✅ 清晰 |
| 可维护性 | 中 | 高 | ⬆️ 提升 |
| 可测试性 | 中 | 高 | ⬆️ 提升 |

### 新增模块

#### 1. image_utils.py (~100 行)
- 镜像路径处理
- 标签操作
- 引用转换
- 文件名安全化

#### 2. filesystem_utils.py (~50 行)
- 文件读写
- SHA256 计算
- Tar 元数据过滤
- 归档锁管理

#### 3. file_content_generator.py (~180 行)
- README 生成
- 镜像清单生成
- 安装脚本生成
- 包索引生成

#### 4. config_manager.py (~220 行)
- 环境变量解析
- 密钥配置管理
- 项目默认配置
- 中间件配置

---

## 🎓 遵循的原则

### Karpathy 渐进式开发法
1. **先跑通再优化**：每个 Phase 都独立可验证
2. **推迟框架引入**：不引入新依赖，纯重构
3. **逐层叠加**：Phase 1 → Phase 2 → Phase 3 → Phase 4
4. **每层验证**：每个 Phase 结束都运行测试
5. **不做过度设计**：只提取明确重复的代码

### 重构黄金法则
1. **测试先行**：重构前确保测试完整
2. **小步快跑**：每次只提取一个模块
3. **持续验证**：每次变更后立即测试
4. **保持功能**：不改变任何行为
5. **及时提交**：每个 Phase 完成后提交

---

## ⚠️ 风险和应对

### 风险 1：测试失败
**应对**：每次提取后立即运行测试，失败立即修复

### 风险 2：循环依赖
**应对**：新模块只依赖标准库和 models，不依赖 builder

### 风险 3：性能下降
**应对**：Phase 4 进行性能对比，发现问题立即优化

### 风险 4：破坏现有功能
**应对**：保持接口不变，只移动实现

---

## 📅 时间规划

| Phase | 任务 | 预估时间 | 累计时间 |
|-------|------|----------|----------|
| Phase 1 | 工具函数模块 | 3-4 天 | 3-4 天 |
| Phase 2 | 内容生成模块 | 3-4 天 | 6-8 天 |
| Phase 3 | 配置管理模块 | 4-5 天 | 10-13 天 |
| Phase 4 | 文档和验收 | 1-2 天 | 11-15 天 |
| **总计** | - | **11-15 天** | **~2-3 周** |

---

## 🚀 开始执行

### 立即行动：Phase 1 - Task 1.1

**任务**：创建 image_utils.py  
**预估时间**：2-3 小时  

**步骤**：
1. 创建文件骨架
2. 提取 10 个镜像处理函数
3. 添加类型注解和文档字符串
4. 编写单元测试（覆盖所有函数）
5. 更新 builder.py 导入
6. 运行测试验证

---

**准备好开始 Phase 1 - Task 1.1 吗？**
