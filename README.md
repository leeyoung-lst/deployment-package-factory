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

## 运行配置

后端支持通过环境变量调整任务执行和产物路径：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEPLOYMENT_PACKAGE_DATA_DIR` | `data/` | 运行时数据根目录 |
| `DEPLOYMENT_PACKAGE_TASK_DB` | `${DEPLOYMENT_PACKAGE_DATA_DIR}/deployment-package-tasks.sqlite3` | 导包任务 SQLite 路径 |
| `DEPLOYMENT_PACKAGE_OUTPUT_DIR` | `${DEPLOYMENT_PACKAGE_DATA_DIR}/deployment-packages` | 工作目录和 tar.gz 产物输出目录 |
| `DEPLOYMENT_PACKAGE_MAX_CONCURRENT_BUILDS` | `1` | 单进程内同时执行的导包任务数 |
| `DEPLOYMENT_PACKAGE_EXECUTION_MODE` | `background` | `background` 由 API 后台任务执行，`worker` 由独立 worker 领取执行 |
| `DEPLOYMENT_PACKAGE_WORKER_POLL_INTERVAL_SECONDS` | `3` | worker 轮询 pending 任务的间隔 |
| `DEPLOYMENT_PACKAGE_WORKER_HEARTBEAT_SECONDS` | `15` | worker 执行 running 任务时刷新心跳的间隔 |
| `DEPLOYMENT_PACKAGE_RUNNING_TASK_TIMEOUT_MINUTES` | `120` | worker 将超时 running 任务标记失败的阈值 |
| `DEPLOYMENT_PACKAGE_RETENTION_DAYS` | `30` | 清理任务保留最近多少天的部署包产物 |
| `DEPLOYMENT_PACKAGE_MAX_TOTAL_GB` | `500` | 清理任务保留的部署包产物总容量上限 |

本地默认使用 FastAPI 后台任务执行导包。生产部署可设置 `DEPLOYMENT_PACKAGE_EXECUTION_MODE=worker`，由 `python -m deployment_package_factory.worker` 独立领取和执行任务。

## 部署部署包工厂

`deploy/` 目录提供部署包工厂自身的生产部署清单：

- `deploy/docker-compose.prod.yml`：单机或轻量环境部署。
- `deploy/k8s/`：Kubernetes namespace、ConfigMap、PVC、Deployment、Service、Ingress 和 Kustomize 入口。

详细步骤见 `deploy/README.md`。

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
- 导包任务支持取消和失败重试，后端默认同一进程内仅允许 1 个构建任务同时执行，其他任务会排队等待执行槽位。独立 worker 模式会记录 `workerId`、领取时间和心跳时间，进程崩溃后的 running 任务会按心跳超时转为 failed 以便重试。
- 生成包会写入 `package-index.json`，按 root/docs/k8s/docker-compose/init/overlays/images/scripts/security 分区登记文件、大小、SHA256 和可执行标记。
- 生成包会写入 `verify.sh`、`verify.ps1` 和 `security/SHA256SUMS`，安装前默认校验文件完整性、包索引和镜像归档锁。

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

根目录索引：

- `manifest.json`
- `package-index.json`
- `README.md`
- `install.sh`
- `install.ps1`
- `verify.sh`
- `verify.ps1`

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

项目专属模板文件可放在 `templates/overlays/<projectKey>/`，导包时会复制到 `overlays/<projectKey>/files/`。推荐目录包括：

- `init/postgres/` 或 `init/dm/`
- `init/minio/`
- `init/qdrant/`
- `init/camunda/`
- `k8s/patches/`

## 部署包质量门禁

安装前建议先执行预检：

```bash
./verify.sh
scripts/check-prerequisites.sh k8s
k8s/dry-run.sh
```

也可以使用根目录统一入口：

```bash
./install.sh k8s
./install.sh docker-compose
./install.sh k8s --yes --skip-dry-run --skip-health-check
./install.sh k8s --yes --skip-verify
```

Windows PowerShell：

```powershell
.\verify.ps1
.\install.ps1 -Mode k8s
.\install.ps1 -Mode docker-compose
.\install.ps1 -Mode k8s -Yes -SkipDryRun -SkipHealthCheck
.\install.ps1 -Mode k8s -Yes -SkipVerify
```

统一入口默认会先执行完整性校验并要求确认。自动化执行时使用 `--yes` 或 `-Yes`，现场已完成预检时可跳过完整性校验、dry-run 或健康检查。

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

取消或重试任务：

```http
POST /api/deployment-packages/tasks/{taskId}/cancel
POST /api/deployment-packages/tasks/{taskId}/retry
```

清理过期产物：

```http
POST /api/deployment-packages/cleanup?dry_run=true
POST /api/deployment-packages/cleanup
```

清理只删除 `artifacts/` 下的 tar.gz 和 `work/` 下的临时目录，不删除任务数据库记录。被清理的包再次下载会返回产物不存在。
任务响应会通过 `artifactAvailable` 标识产物是否仍可下载，前端会在产物已清理时禁用下载入口。

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
