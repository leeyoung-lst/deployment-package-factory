# P0 任务执行计划 - 工作区清理

## 📊 变更统计总览

**总变更**：30 个文件  
**新增代码**：+1,102 行  
**删除代码**：-51 行  
**净增长**：+1,051 行

---

## 🗂️ 变更分类分析

### 📦 分组 1：微服务脚手架核心功能（高优先级）
**影响**：8 个后端文件 + 5 个测试文件 = 13 个文件  
**代码量**：+691 行

#### 后端模块
1. `backend/deployment_package_factory/services/microservices/scaffold.py` (+157 行)
2. `backend/deployment_package_factory/services/microservices/node_templates.py` (+69 行)
3. `backend/deployment_package_factory/services/microservices/validation.py` (+52 行)
4. `backend/deployment_package_factory/services/microservices/templates.py` (+11 行)
5. `backend/deployment_package_factory/services/microservices/repository.py` (+6 行)
6. `backend/deployment_package_factory/api/microservices.py` (+1 行)

#### 测试文件
7. `backend/tests/test_microservice_scaffold_api.py` (+151 行)

#### 未跟踪的新文件
8. `backend/deployment_package_factory/services/microservices/feature_specs.py` (新文件)
9. `backend/deployment_package_factory/services/microservices/mcp_templates.py` (新文件)

**功能描述**：
- 微服务脚手架生成能力增强
- Node.js 模板完善
- 验证逻辑增强
- 仓库推送功能
- 完整的测试覆盖

**提交建议**：
```
feat: 增强微服务脚手架生成能力

核心改进：
- 扩展 scaffold.py：支持更多技术栈和配置选项
- 完善 node_templates.py：增强 Node.js 项目模板
- 强化 validation.py：添加更严格的输入验证
- 新增 feature_specs.py：功能规格定义
- 新增 mcp_templates.py：MCP 相关模板

测试覆盖：
- 新增 151 行测试用例
- 覆盖所有新增功能

影响范围：微服务注册和脚手架生成流程
```

---

### 🎨 分组 2：前端微服务向导（高优先级）
**影响**：8 个前端文件  
**代码量**：+54 行

#### 前端组件
1. `frontend/src/api/microservices.ts` (+14 行)
2. `frontend/src/views/components/MicroserviceResultContent.tsx` (+14 行)
3. `frontend/src/views/components/microserviceWizard/DependencyStep.tsx` (+9 行)
4. `frontend/src/api/deploymentPackages.ts` (+6 行)
5. `frontend/src/views/components/RegisteredMicroservicesPanel.tsx` (+3 行)
6. `frontend/src/views/hooks/useMicroserviceRegistration.ts` (+3 行)
7. `frontend/src/views/components/MicroserviceRegistrationWizard.tsx` (+2 行)
8. `frontend/src/views/components/microserviceWizard/TechStackStep.tsx` (+2 行)
9. `frontend/src/views/components/microserviceWizard/SummaryStep.tsx` (+1 行)

**功能描述**：
- API 客户端更新（支持新的后端接口）
- 结果展示增强
- 依赖选择步骤优化
- 面板和向导 UI 改进

**提交建议**：
```
feat: 前端微服务向导 UI 增强

核心改进：
- 更新 API 客户端，对接新的后端接口
- 增强结果展示组件，提供更丰富的反馈
- 优化依赖选择步骤用户体验
- 完善向导各步骤的交互逻辑

影响范围：微服务注册向导前端界面
```

**依赖关系**：依赖分组 1（后端 API 变更）

---

### 📋 分组 3：部署包渲染器增强（中优先级）
**影响**：3 个后端文件 + 3 个测试文件 = 6 个文件  
**代码量**：+245 行

#### 后端模块
1. `backend/deployment_package_factory/services/deployment_packages/init_script_renderer.py` (+215 行)
2. `backend/deployment_package_factory/services/deployment_packages/acceptance_report_renderer.py` (+21 行)
3. `backend/deployment_package_factory/services/deployment_packages/quality_renderer.py` (+9 行)

#### 测试文件
4. `backend/tests/test_deployment_package_builder.py` (+21 行)
5. `backend/tests/test_acceptance_report_renderer.py` (+13 行)
6. `backend/tests/test_deployment_package_api.py` (+11 行)
7. `backend/tests/test_quality_renderer.py` (+3 行)

#### 未跟踪的新文件
8. `backend/deployment_package_factory/services/deployment_packages/mcp_verify_renderer.py` (新文件)
9. `backend/tests/test_mcp_verify_renderer.py` (新文件)

**功能描述**：
- 初始化脚本渲染器大幅增强（+215 行）
- 验收报告渲染器改进
- 质量门禁渲染器更新
- MCP 验证渲染器（新功能）

**提交建议**：
```
feat: 增强部署包渲染能力

核心改进：
- 大幅扩展 init_script_renderer.py：支持更多初始化场景
- 完善 acceptance_report_renderer.py：增强验收报告生成
- 优化 quality_renderer.py：提升质量检查覆盖
- 新增 mcp_verify_renderer.py：MCP 验证功能

测试覆盖：
- 新增 48 行测试用例
- 覆盖所有渲染器变更

影响范围：部署包内容生成逻辑
```

---

### 🚀 分组 4：生产部署配置（中优先级）
**影响**：3 个文件  
**代码量**：+182 行

#### 部署文件
1. `deploy/README.md` (+173 行)
2. `deploy/k8s/ingress.yaml` (+5 行)
3. `deploy/k8s/worker.yaml` (+4 行)
4. `backend/Dockerfile.worker` (+2 行)

**功能描述**：
- 部署文档大幅扩充（+173 行）
- K8s Ingress 配置更新
- Worker 部署配置优化
- Worker Dockerfile 调整

**提交建议**：
```
docs: 完善生产部署文档和配置

核心改进：
- 大幅扩展 deploy/README.md：详细部署指南
- 更新 K8s Ingress 配置：路由规则优化
- 优化 Worker 部署配置：资源和健康检查
- 调整 Worker Dockerfile：镜像构建优化

影响范围：生产环境部署流程
```

---

### 📊 分组 5：项目模板数据（低优先级）
**影响**：2 个文件  
**代码量**：+173 行

#### 模板文件
1. `templates/overlays/standard-eam/init/camunda/eam-repair.bpmn` (+112 行)
2. `templates/overlays/mes-lite/init/dm/010_mes_lite_schema.sql` (+61 行)

#### 未跟踪目录
3. `templates/overlays/standard-eam/init/postgres/` (新目录)

**功能描述**：
- EAM 维修流程 BPMN 定义
- MES Lite 达梦数据库初始化脚本
- Standard EAM PostgreSQL 初始化脚本（新增）

**提交建议**：
```
feat: 更新项目模板初始化资产

核心改进：
- 更新 eam-repair.bpmn：完善维修工单流程定义
- 扩展 MES Lite 达梦数据库初始化脚本
- 新增 Standard EAM PostgreSQL 初始化脚本

影响范围：项目模板初始化数据
```

---

### 📄 分组 6：任务报告文档（低优先级）
**影响**：2 个文件

#### 文档文件
1. `FINAL_REPORT.md` (新文件)
2. `TASK_COMPLETION.md` (新文件)

**提交建议**：
```
docs: 添加任务完成报告

- 添加最终报告文档
- 添加任务完成确认文档

这些是临时工作文档，可选择不提交或后续删除
```

---

## 🎯 推荐提交顺序

### 第 1 批：后端核心功能（分组 1 + 分组 3）
**原因**：独立的后端逻辑，不影响前端

```bash
# 1. 微服务脚手架核心
git add backend/deployment_package_factory/services/microservices/
git add backend/deployment_package_factory/api/microservices.py
git add backend/tests/test_microservice_scaffold_api.py
git commit -m "feat: 增强微服务脚手架生成能力"

# 2. 部署包渲染器
git add backend/deployment_package_factory/services/deployment_packages/
git add backend/tests/test_acceptance_report_renderer.py
git add backend/tests/test_deployment_package_builder.py
git add backend/tests/test_deployment_package_api.py
git add backend/tests/test_quality_renderer.py
git add backend/tests/test_init_script_renderer.py
git commit -m "feat: 增强部署包渲染能力"
```

### 第 2 批：前端 UI（分组 2）
**原因**：依赖第 1 批的后端 API

```bash
git add frontend/src/
git commit -m "feat: 前端微服务向导 UI 增强"
```

### 第 3 批：部署配置（分组 4）
**原因**：基础设施配置，影响独立

```bash
git add deploy/
git add backend/Dockerfile.worker
git commit -m "docs: 完善生产部署文档和配置"
```

### 第 4 批：项目模板（分组 5）
**原因**：数据文件，影响最小

```bash
git add templates/overlays/
git commit -m "feat: 更新项目模板初始化资产"
```

### 第 5 批：文档（分组 6 - 可选）
**原因**：临时文档，可以选择不提交

```bash
# 选项 A：不提交（推荐）
git restore --staged FINAL_REPORT.md TASK_COMPLETION.md

# 选项 B：提交
git add FINAL_REPORT.md TASK_COMPLETION.md
git commit -m "docs: 添加任务完成报告"
```

---

## ✅ 验证检查清单

在每次提交前执行：

```bash
# 1. 运行测试
cd backend && pytest

# 2. 代码格式检查（如果有）
# ruff check backend/
# black --check backend/

# 3. 查看提交内容
git diff --cached

# 4. 确认提交
git status
```

---

## 🎯 下一步行动

**准备好开始了吗？**

我可以：
1. ✅ 直接帮你执行上述 5 批提交
2. ✅ 逐批审查变更内容后再提交
3. ✅ 先运行测试验证功能完整性
4. ✅ 调整提交顺序或分组策略

**请告诉我你的选择！**
