# 部署包工厂与环境隔离实施计划

版本：V1.0
日期：2026-06-27
来源设计：[平台化环境隔离与生产部署包导出中心详细设计](./deployment-package-factory-detailed-design.md)


## 0. 当前落地仓库与路径映射

本实施计划的最终落地形态已调整为独立 Git 仓库：

```text
D:\project\work\li-yong\deployment-package-factory
```

路径映射如下：

| 早期计划路径 | 独立仓库实际路径 |
| --- | --- |
| `backend/deployment_package_factory/api/deployment_packages.py` | `backend/deployment_package_factory/api/deployment_packages.py` |
| `backend/deployment_package_factory/services/deployment_packages/` | `backend/deployment_package_factory/services/deployment_packages/` |
| `frontend/src/views/DeploymentPackageExportView.tsx` | `frontend/src/views/DeploymentPackageExportView.tsx` |
| `templates/catalog/` | `templates/catalog/` |

`local-ai-assistant` 主业务仓库不注册导包 API、不挂载导包菜单。导包工厂通过能力目录和项目模板描述要导出的基础平台与业务产品。
## 1. 实施目标

基于独立 Git 仓库 `deployment-package-factory`，面向 `local-ai-assistant` 及后续业务平台分阶段实现：

```text
dev/test 环境隔离
基础平台服务与业务平台服务分层
中间件国产化/非国产化选择
导包页面
K8s / Docker Compose 生产部署包生成
镜像、初始化脚本、安装文档一键导出
```

本计划采用：

```text
大任务 -> 中任务 -> 小任务 -> 验收标准
```

每个小任务都应能独立验证，避免一次性大改。

## 2. 里程碑总览

| 里程碑 | 目标 | 主要产物 |
| --- | --- | --- |
| M1 环境与部署分层 | dev/test/base-public/business/middleware 结构落地 | Helm values、namespace、label、NetworkPolicy |
| M2 能力目录与依赖推导 | 用配置描述平台能力、业务能力、中间件依赖 | catalog、resolver、单元测试 |
| M3 导包任务后端 | 支持预览、创建任务、任务状态、打包框架 | API、task repo、builder、archive |
| M4 K8s/Compose 生成 | 生成可安装的 K8s YAML 与 Docker Compose | renderer、模板、dry-run 校验 |
| M5 初始化脚本与 Secret 模板 | 生成数据库/MinIO/Qdrant/Camunda 初始化脚本 | init scripts、secret-check |
| M6 镜像导出与包完整性 | 支持镜像清单、tar 导出、SHA256 | image exporter、SHA256SUMS |
| M7 导包页面 | 页面完成选择、预览、生成、进度、下载 | React 页面、API client、权限接入 |
| M8 生产化硬化 | Worker、安全、审计、保留策略、异常重试 | worker、审计、清理任务、质量门禁 |

## 3. 大任务 A：环境与部署分层

目标：让当前项目先具备 dev/test 两套环境，并把基础平台、业务服务、中间件分层部署。

### A1. Namespace 与标签规范落地

小任务：

1. 新增 dev/test namespace 命名规范文档。
2. 在 Helm values 中增加 `global.env`、`global.layer`、`global.namespacePrefix`。
3. Deployment 模板统一增加标签：
   - `local-ai/env`
   - `local-ai/layer`
   - `local-ai/domain`
   - `local-ai/product`
4. Service、PodDisruptionBudget、NetworkPolicy 同步增加选择标签。

涉及文件：

```text
infra/helm/local-ai-apps/templates/deployments.yaml
infra/helm/local-ai-apps/templates/services.yaml
infra/helm/local-ai-data/templates/deployments.yaml
infra/helm/local-ai-platform/templates/namespace.yaml
infra/helm/local-ai-*/values.yaml
```

验收标准：

- `helm template` 输出的 Pod 都包含统一标签。
- dev/test 的 YAML 中 namespace 不再固定为 `local-ai`。
- `local-ai/env=dev` 与 `local-ai/env=test` 可被 kubectl label selector 区分。

### A2. dev/test values 目录

小任务：

1. 新增：

```text
infra/helm/values/dev/
  base-public.yaml
  business-eam.yaml
  middleware.yaml

infra/helm/values/test/
  base-public.yaml
  business-eam.yaml
  middleware.yaml
```

2. dev/test 配置分离：
   - DATABASE_URL
   - REDIS_URL
   - MINIO bucket
   - QDRANT_COLLECTION
   - IOTDB_DATABASE
   - CAMUNDA_BASE_URL
3. 前端 `config.json` 在 dev/test 中分别指向对应子应用地址。

验收标准：

- dev/test 可以分别渲染 Helm YAML。
- dev/test 数据库、Redis、MinIO bucket 名称不同。
- dev/test 前端微应用配置不同。

### A3. 分层 NetworkPolicy

小任务：

1. middleware namespace 默认仅允许同环境 base-public/business 访问。
2. business namespace 允许访问同环境 base-public 与 middleware。
3. dev 与 test 默认互不可访问。
4. 业务 namespace 之间默认禁止互访。

验收标准：

- dev-business-eam 无法访问 test-middleware。
- dev-business-eam 可以访问 dev-base-public IAM。
- dev-business-eam 可以访问 dev-middleware Redis/DB。

### A4. 环境部署脚本

小任务：

1. 新增 `scripts/deploy-env-render.ps1` 或 `.sh`。
2. 支持参数：

```text
--env dev
--layer base-public|business-eam|middleware
--output .tmp-deploy/dev
```

3. 输出 Helm 渲染结果。

验收标准：

- 一条命令可渲染 dev 全套 YAML。
- 一条命令可渲染 test 全套 YAML。
- 脚本失败时输出具体 chart 和 values 文件。

## 4. 大任务 B：能力目录与依赖推导

目标：让页面选择能力时，系统可以自动推导基础服务、中间件、镜像和 namespace。

### B1. 能力目录模板

小任务：

1. 新增目录：

```text
templates/catalog/
  platform.yaml
  business.yaml
  middleware.yaml
  dependency-rules.yaml
```

2. 写入基础平台能力：
   - IAM
   - AI/Agent
   - File/Documents
   - Workflow/Camunda
   - Audit
   - Gateway/Frontend Shell
3. 写入业务能力：
   - EAM
   - MES
   - ERP
   - APS
4. 写入数据库二选一：
   - dm
   - postgres

验收标准：

- catalog 文件可被后端读取。
- 每个服务都有 key、name、namespaceGroup、images、middleware。
- 数据库选项有且仅有 dm/postgres 两类。

### B2. 后端 catalog loader

小任务：

1. 新增：

```text
backend/deployment_package_factory/services/deployment_packages/catalog.py
backend/deployment_package_factory/services/deployment_packages/models.py
```

2. 使用 Pydantic 定义：
   - PlatformCapability
   - BusinessCapability
   - MiddlewareCapability
   - DatabaseOption
3. 校验能力 key 唯一。
4. 校验业务服务必须声明 namespaceGroup。

验收标准：

- 单元测试覆盖 catalog 正常加载。
- catalog 缺字段时报明确错误。
- 重复 key 被拒绝。

### B3. 依赖推导器

小任务：

1. 新增：

```text
backend/deployment_package_factory/services/deployment_packages/dependency_resolver.py
```

2. 实现：
   - 用户选择业务服务后自动补齐基础平台服务。
   - 用户选择基础平台服务后自动补齐中间件。
   - 数据库 dm/postgres 二选一。
   - 自动生成 locked reason。
3. 返回完整预览结构。

验收标准：

- 选择 EAM 自动补齐 IAM/Gateway/File/Workflow/Audit。
- 选择 AI/Agent 自动补齐 Redis/Qdrant/Audit。
- Redis/MinIO/Camunda/Qdrant 展示 requiredBy。
- 同时选择 dm/postgres 会被拒绝。

## 5. 大任务 C：导包任务后端

目标：提供导包 API、任务状态、异步任务框架。

### C1. API 路由

小任务：

1. 新增：

```text
backend/deployment_package_factory/api/deployment_packages.py
```

2. 实现接口：

```text
GET  /api/deployment-packages/options
POST /api/deployment-packages/preview
POST /api/deployment-packages
GET  /api/deployment-packages/{id}
GET  /api/deployment-packages/{id}/download
DELETE /api/deployment-packages/{id}
```

3. 接入 IAM 权限：
   - `platform.deploymentPackage.view`
   - `platform.deploymentPackage.create`
   - `platform.deploymentPackage.download`
   - `platform.deploymentPackage.delete`

验收标准：

- 无权限用户无法创建导包任务。
- 预览接口能返回自动推导结果。
- 创建任务返回 queued 状态。

### C2. 任务状态模型

小任务：

1. 新增 task repo：

```text
backend/deployment_package_factory/services/deployment_packages/task_repo.py
```

2. 支持状态：

```text
queued
running
rendering
exporting_images
generating_docs
archiving
completed
failed
canceled
```

3. 保存：
   - 请求参数
   - 进度
   - 当前阶段
   - 错误信息
   - artifact_path
   - sha256

验收标准：

- 创建任务后能查询。
- 任务失败能记录 failedPhase、message、suggestion。
- 删除任务不删除审计记录。

### C3. Builder 编排

小任务：

1. 新增：

```text
backend/deployment_package_factory/services/deployment_packages/builder.py
backend/deployment_package_factory/services/deployment_packages/archive.py
```

2. Builder 阶段：
   - 创建工作目录。
   - 写入 `manifest.json`。
   - 调用 K8s renderer。
   - 调用 Compose renderer。
   - 调用 docs renderer。
   - 打包 tar.gz。
3. 第一阶段先不导出镜像，只生成镜像清单。

验收标准：

- 可生成一个不含镜像 tar 的部署包。
- 包内包含 README、manifest、k8s、docker-compose 目录。
- 生成过程可重复运行，不污染上一次任务目录。

## 6. 大任务 D：K8s 与 Docker Compose 生成

### D1. K8s renderer

小任务：

1. 新增：

```text
backend/deployment_package_factory/services/deployment_packages/helm_renderer.py
```

2. 根据导包请求生成：
   - `k8s/namespaces.yaml`
   - `k8s/base-public.yaml`
   - `k8s/business-eam.yaml`
   - `k8s/middleware.yaml`
   - `k8s/networkpolicies.yaml`
   - `k8s/secrets.template.yaml`
3. 第一阶段使用 `helm template` 输出纯 YAML。

验收标准：

- K8s 模式包内 YAML 文件完整。
- `kubectl apply --dry-run=client` 或 `--dry-run=server` 可通过。
- namespace 与所选环境/目标前缀一致。

### D2. Docker Compose renderer

小任务：

1. 新增：

```text
backend/deployment_package_factory/services/deployment_packages/compose_renderer.py
```

2. 生成：
   - `docker-compose/docker-compose.yml`
   - `docker-compose/.env.template`
   - `docker-compose/install.sh`
   - `docker-compose/health-check.sh`
3. 使用 networks 模拟 namespace：
   - base-public
   - business-eam
   - business-mes
   - middleware

验收标准：

- `docker compose config` 通过。
- 选择达梦时 compose 不包含 postgres。
- 选择 postgres 时 compose 不包含 dm。
- EAM service 同时连接 business-eam、base-public、middleware 网络。

### D3. 渲染校验

小任务：

1. K8s YAML 增加 kubeconform/kubeval 可选校验。
2. Compose 增加 `docker compose config` 校验。
3. 校验失败时任务进入 failed，返回具体文件和错误。

验收标准：

- 模板变量缺失时可以被测试捕获。
- Compose 语法错误不会生成 completed 包。

## 7. 大任务 E：初始化脚本与 Secret 模板

### E1. Secret 模板

小任务：

1. 生成：

```text
k8s/secrets.template.yaml
k8s/secrets.example.yaml
docker-compose/.env.template
scripts/secret-check.sh
```

2. 检查占位符：
   - `__REPLACE_WITH_DATABASE_PASSWORD__`
   - `__REPLACE_WITH_REDIS_PASSWORD__`
   - `__REPLACE_WITH_MINIO_PASSWORD__`
   - `__REPLACE_WITH_JWT_SECRET__`

验收标准：

- 未替换 Secret 时安装脚本失败。
- 示例 Secret 不包含真实敏感值。

### E2. 数据库初始化脚本

小任务：

1. 生成：

```text
init/postgres/
init/dm/
```

2. 包含：
   - schema 初始化
   - IAM 默认角色/权限
   - EAM 默认权限资源
   - 管理员初始化
3. 所有脚本幂等。

验收标准：

- Postgres 脚本可重复执行。
- DM 脚本与 Postgres 脚本分离。
- 选择 DM 时只打包 DM 初始化脚本为主路径。

### E3. 中间件初始化脚本

小任务：

1. MinIO bucket 初始化。
2. Qdrant collection 初始化。
3. Camunda BPMN 部署脚本。
4. IoTDB 初始化脚本。

验收标准：

- MinIO bucket 存在时跳过。
- Qdrant collection 存在时校验维度。
- Camunda 流程重复部署有 version/tag 说明。

## 8. 大任务 F：镜像导出与包完整性

### F1. 镜像模式

小任务：

1. 支持三种模式：
   - image-manifest
   - image-tar
   - image-push
2. `manifest.json` 记录 imageMode。
3. 页面和 API 校验 image-push 必须提供目标 registry。

验收标准：

- 仅清单模式不执行 docker save。
- tar 模式生成 images 目录。
- push 模式生成推送日志。

### F2. 镜像导出器

小任务：

1. 新增：

```text
backend/deployment_package_factory/services/deployment_packages/image_exporter.py
```

2. 支持 docker 和 containerd 两种运行模式。
3. 生成：
   - `scripts/load-images.sh`
   - `scripts/push-images.sh`
   - `security/image-digest-lock.json`

验收标准：

- 镜像不存在时给出明确错误和建议。
- 导出的 tar 有 sha256。
- load-images.sh 可重复执行。

### F3. 完整性校验

小任务：

1. 生成：

```text
security/SHA256SUMS
security/artifact-manifest.json
```

2. 计算：
   - 镜像 tar sha256
   - YAML sha256
   - compose 文件 sha256
   - 最终 tar.gz sha256

验收标准：

- 包下载接口返回 sha256。
- 本地执行 `sha256sum -c security/SHA256SUMS` 通过。

## 9. 大任务 G：导包页面

### G1. API client

小任务：

1. 新增：

```text
frontend/src/api/deploymentPackages.ts
```

2. 封装：
   - getOptions
   - previewDeploymentPackage
   - createDeploymentPackage
   - getDeploymentPackageTask
   - downloadDeploymentPackage

验收标准：

- API client 有类型定义。
- 错误响应能显示 message。

### G2. 页面主体

小任务：

1. 新增：

```text
frontend/src/views/DeploymentPackageExportView.tsx
```

2. 页面包含：
   - 来源环境。
   - 部署方式。
   - 基础平台服务。
   - 业务平台服务。
   - 数据库二选一。
   - 自动匹配中间件。
   - 生产参数。
   - 包内容预览。
3. 自动依赖锁定原因可见。

验收标准：

- 选择 EAM 后自动勾选依赖。
- 被依赖锁定项不可取消，并显示原因。
- 数据库只能二选一。

### G3. 任务进度与下载

小任务：

1. 生成任务后显示：
   - 任务编号。
   - 当前状态。
   - 当前阶段。
   - 进度。
   - 日志。
2. 完成后显示：
   - 文件名。
   - 大小。
   - SHA256。
   - 下载按钮。
3. 失败时显示：
   - failedPhase。
   - message。
   - suggestion。
   - 是否可重试。

验收标准：

- completed 状态可以下载包。
- failed 状态显示恢复建议。
- 无权限用户看不到创建按钮或提交时报 403。

### G4. 菜单与权限

小任务：

1. 注册菜单：
   - 运维中心 / 部署包导出中心。
2. 注册权限：
   - `platform.deploymentPackage.view`
   - `platform.deploymentPackage.create`
   - `platform.deploymentPackage.download`
   - `platform.deploymentPackage.delete`
3. 前端按权限展示按钮。

验收标准：

- 无 view 权限看不到菜单。
- 无 create 权限不能生成包。
- 无 download 权限不能下载包。

## 10. 大任务 H：Worker 与生产化硬化

### H1. Worker 服务

小任务：

1. 新增 worker 入口：

```text
backend/deployment_package_factory/worker.py
backend/Dockerfile.deployment-package-worker
```

2. Worker 从任务表或队列领取任务。
3. Worker 支持并发上限配置。
4. Worker 支持取消任务检查。

验收标准：

- API 进程不直接执行 docker save。
- Worker 独立部署。
- Worker 崩溃后任务可标记失败或重新领取。

### H2. 包存储与清理

小任务：

1. 配置：

```text
DEPLOYMENT_PACKAGE_DIR
DEPLOYMENT_PACKAGE_RETENTION_DAYS
DEPLOYMENT_PACKAGE_MAX_TOTAL_GB
```

2. 定时清理过期包。
3. 已归档包不清理。

验收标准：

- 超过保留期的包可被清理。
- 任务元数据和审计记录保留。

### H3. 审计

小任务：

1. 增加事件：
   - deployment_package.previewed
   - deployment_package.created
   - deployment_package.completed
   - deployment_package.failed
   - deployment_package.downloaded
   - deployment_package.deleted
2. 记录选择服务、数据库、镜像模式、包 sha256。

验收标准：

- 每次创建、完成、失败、下载都有审计记录。
- 审计查询能按用户和时间过滤。

## 11. 大任务 I：质量门禁与测试

### I1. 后端测试

小任务：

1. 新增测试：

```text
backend/tests/test_deployment_package_catalog.py
backend/tests/test_deployment_package_dependency_resolver.py
backend/tests/test_deployment_package_api.py
backend/tests/test_deployment_package_builder.py
```

2. 覆盖：
   - catalog 校验。
   - EAM 依赖推导。
   - 数据库互斥。
   - 无权限创建失败。
   - 生成包目录结构。

验收标准：

- pytest 通过。
- 关键失败路径有测试。

### I2. 前端测试

小任务：

1. 新增页面测试。
2. 覆盖：
   - EAM 选择后依赖自动勾选。
   - 数据库二选一。
   - 锁定原因展示。
   - failed 状态展示建议。

验收标准：

- Vitest 通过。
- 页面核心交互有断言。

### I3. 包质量校验

小任务：

1. K8s YAML 校验。
2. Compose config 校验。
3. shellcheck。
4. sha256 校验。

验收标准：

- 生成包必须通过质量门禁才能标记 completed。
- 任一门禁失败则任务 failed 并显示错误文件。

## 12. 推荐实施顺序

```text
第 1 批：A1、A2、B1、B2
  先让环境和值配置有基础，再让能力目录可读。

第 2 批：B3、C1、C2
  打通 options/preview/create/task 查询。

第 3 批：C3、D1、D2
  生成第一个不含镜像的部署包。

第 4 批：E1、E2、E3
  补齐初始化脚本和 Secret 模板。

第 5 批：G1、G2、G3、G4
  完成导包页面。

第 6 批：F1、F2、F3
  接入镜像导出和完整性校验。

第 7 批：H1、H2、H3
  Worker 化、清理策略、审计闭环。

第 8 批：I1、I2、I3
  质量门禁与回归测试补齐。
```

## 13. 总体验收标准

### 13.1 环境隔离验收

- dev/test 可分别渲染并部署。
- dev/test 数据库、Redis、MinIO、Qdrant 配置不混用。
- dev/test 网络默认互相隔离。
- business namespace 只能访问同环境 base-public 和 middleware。

### 13.2 导包功能验收

- 页面可选择 K8s、Docker Compose 或两者。
- 页面可选择基础平台服务和业务平台服务。
- 页面可选择达梦或 PostgreSQL，且只能二选一。
- 选择 EAM 后自动补齐 IAM/Gateway/File/Workflow/Audit 和所需中间件。
- 生成包包含 manifest、README、K8s、Compose、初始化脚本、Secret 模板。

### 13.3 镜像与离线验收

- 支持仅镜像清单模式。
- 支持完整镜像 tar 模式。
- 支持镜像 sha256 校验。
- 离线环境可执行 `load-images.sh`。

### 13.4 安全验收

- Secret 只生成模板。
- 未替换 Secret 时安装脚本拒绝执行。
- 无权限用户不能创建、下载、删除导包。
- 导包创建、失败、完成、下载均有审计。

### 13.5 质量验收

- K8s YAML 通过 dry-run 或 schema 校验。
- Docker Compose 通过 `docker compose config`。
- 初始化脚本可重复执行。
- 失败任务显示明确 failedPhase、message、suggestion。
- 任务 completed 前必须生成 SHA256SUMS。

## 14. 首个 MVP 范围建议

为了尽快闭环，首个 MVP 不建议一次性支持所有业务和镜像导出。

MVP 范围：

```text
部署方式：
  K8s + Docker Compose

基础平台：
  IAM
  Gateway / Frontend Shell
  Audit

业务平台：
  EAM

数据库：
  PostgreSQL

中间件：
  Redis
  MinIO
  Camunda

镜像模式：
  仅生成镜像清单

输出：
  manifest.json
  README.md
  k8s YAML
  docker-compose.yml
  secrets.template
  init scripts
```

MVP 验收：

- 页面选择 EAM 后能生成一个不含镜像 tar 的生产部署包。
- K8s YAML 和 Compose 文件通过语法校验。
- 包内文档和初始化脚本齐全。
- 导包任务有状态、有审计、可下载。

第二阶段再补：

```text
达梦
AI/Agent
File/Documents
Workflow/Camunda 完整能力
镜像 tar 导出
Worker 独立部署
MES/ERP/APS
```
