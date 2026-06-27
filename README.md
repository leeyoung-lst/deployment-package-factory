# Deployment Package Factory

独立部署包导出项目，用于从开发环境或测试环境选择基础平台能力、业务产品和中间件依赖，生成生产交付包。

## 项目结构

- `backend/`: 独立 FastAPI 服务，提供能力目录、依赖预览、部署包生成和下载接口。
- `frontend/`: 独立 Vite + React 页面，面向实施人员执行导包。
- `templates/catalog/`: 基础平台、业务产品、中间件、项目模板和依赖规则目录。
- `data/deployment-packages/`: 默认部署包输出目录，运行时生成。

## 本地运行

后端：

```powershell
cd deployment-package-factory/backend
uvicorn deployment_package_factory.main:app --reload --port 8096
```

前端：

```powershell
cd deployment-package-factory/frontend
pnpm install
pnpm dev
```

前端开发服务默认代理 `/api` 到 `http://127.0.0.1:8096`。

也可以直接启动容器化版本：

```powershell
cd deployment-package-factory
docker compose up --build
```

访问 `http://127.0.0.1:5186`。

## 当前能力

- 支持 `dev`、`test` 来源环境。
- 支持 `k8s`、`docker-compose` 部署方式选择。
- 基础平台能力包括 IAM、AI / Agent、File / Documents、Workflow / Camunda、Audit、Gateway / Frontend Shell。
- 业务产品包括 EAM、MES、ERP、APS。
- 项目模板支持默认产品版本、业务组合、数据库、镜像仓库、命名空间前缀、域名、StorageClass 和 overlay 标识。
- 数据库在达梦 DM 与 PostgreSQL 中二选一。
- 中间件依赖按所选基础能力和业务产品自动解析。
- 生成包包含 manifest、安装文档、K8s namespace、Docker Compose 样例、初始化脚本占位、质量门禁脚本和安全摘要。
- 镜像清单模式会生成 `images/images.txt`、`scripts/pull-images.sh`、`scripts/save-images.sh`、`scripts/load-images.sh`。
- 镜像归档模式会调用本机 Docker CLI 执行 `docker pull` 和 `docker save`，将镜像 tar 写入 `images/archives/` 并记录 SHA256。
- K8s 模式会生成 Namespace、ConfigMap、Secret 模板、PVC、Deployment、Service、Ingress、数据库初始化 Job、安装、卸载和 dry-run 脚本。
- Docker Compose 模式会生成基础平台、业务平台、中间件服务、网络、卷、安装、卸载和 dry-run 脚本。
- 导包请求采用后台任务模式执行，任务状态、进度、日志和失败原因会持久化到 SQLite。

## 镜像导出模式

`image-manifest` 适合在没有 Docker 或不希望立即拉取镜像时使用，部署包只包含镜像清单和脚本：

```bash
scripts/pull-images.sh
scripts/save-images.sh
```

`image-archive` 适合制作离线包。运行导包后端的机器必须已安装 Docker CLI，并且能够访问来源镜像仓库。失败时 API 会返回明确的 400 错误，例如 Docker 不可用或镜像拉取失败。

生产侧导入镜像：

```bash
scripts/load-images.sh
```

## 部署模板产物

K8s 产物位于 `k8s/`：

- `namespaces.yaml`
- `configmaps.yaml`
- `secrets.template.yaml`
- `pvcs.yaml`
- `deployments.yaml`
- `services.yaml`
- `ingress.yaml`
- `jobs/init-db.yaml`
- `install.sh`
- `uninstall.sh`
- `dry-run.sh`

Docker Compose 产物位于 `docker-compose/`：

- `docker-compose.yml`
- `.env.template`
- `install.sh`
- `uninstall.sh`
- `dry-run.sh`

通用脚本位于 `scripts/`：

- `check-prerequisites.sh`
- `secret-check.sh`
- `health-check.sh`

初始化脚本位于 `init/`：

- `run-init.sh`
- `postgres/001_schema.sql` 或 `dm/001_schema.sql`
- `minio/create-buckets.sh`
- `qdrant/create-collections.sh`
- `camunda/bootstrap-admin.sh`

`run-init.sh` 是统一入口。Docker Compose 安装脚本会在服务启动后调用它；K8s 包会生成 `jobs/init-db.yaml`，用于在目标集群中执行初始化入口。当前初始化内容为可审计、可重复执行的生产占位模板，现场交付时可按项目补齐真实 SQL、bucket、collection 和 Camunda 模型导入。

项目级 overlay 位于 `overlays/<projectKey>/`：

- `values.json`
- `kustomization.yaml`
- `README.md`

项目模板中的 `imageTag` 会作为无显式 tag 镜像的默认版本；`overlays` 会写入 overlay values 和 Kustomize labels，便于后续叠加项目级 SQL、BPMN、对象存储策略和 YAML patch。

## 部署包质量门禁

安装前建议先执行预检：

```bash
scripts/check-prerequisites.sh k8s
k8s/dry-run.sh
```

或 Docker Compose：

```bash
scripts/check-prerequisites.sh docker-compose
docker-compose/dry-run.sh
```

`k8s/install.sh` 和 `docker-compose/install.sh` 会自动调用 `scripts/secret-check.sh`。K8s 模式会优先检查 `k8s/secrets.yaml`，不存在时检查 `k8s/secrets.template.yaml`；Docker Compose 模式会优先检查 `docker-compose/.env`，不存在时检查 `.env.template`。如果目标文件中仍存在 `__REPLACE_WITH_` 占位符，安装会直接失败，避免把未替换的生产密钥配置带入目标环境。

部署后可执行：

```bash
scripts/health-check.sh k8s
scripts/health-check.sh docker-compose
```

## 任务接口

创建导包任务：

```http
POST /api/deployment-packages
```

查询任务：

```http
GET /api/deployment-packages/tasks/{taskId}
GET /api/deployment-packages/tasks
```

下载部署包：

```http
GET /api/deployment-packages/{packageId}/download
```

## 项目模板

项目模板定义在 `templates/catalog/projects.yaml`。每个项目可以配置：

- `defaultVersion`
- `versions`
- `defaultSourceEnv`
- `defaultDeployModes`
- `defaultPlatformServices`
- `defaultBusinessServices`
- `defaultDatabase`
- `registry`
- `namespacePrefix`
- `domain`
- `storageClass`
- `imageTag`
- `overlays`

前端选择项目后会自动套用这些默认值；后端在预览和构建时也会校验并应用项目配置。

## 后续硬化

- 增加任务取消、重试和并发队列限制。
- 按项目模板扩展 Helm/Kustomize overlay。
- 增加离线安装校验。
- 将初始化占位模板升级为项目级真实 SQL、BPMN 和对象存储策略。
