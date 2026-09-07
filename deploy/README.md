# Deployment Package Factory 部署说明

本目录用于部署“部署包工厂”自身，而不是它生成的业务生产部署包。

## 镜像

默认镜像名：

```text
deployment-package-factory-backend:latest
deployment-package-factory-worker:latest
deployment-package-factory-frontend:latest
```

构建示例：

```bash
scripts/build-images.sh --tag latest
```

Windows PowerShell：

```powershell
.\scripts\build-images.ps1 -Tag latest
```

构建并推送到镜像仓库：

```bash
scripts/build-images.sh --registry registry.example.com --repository platform --tag 2026.06
scripts/push-images.sh --registry registry.example.com --repository platform --tag 2026.06
```

Windows PowerShell：

```powershell
.\scripts\build-images.ps1 -Registry registry.example.com -Repository platform -Tag 2026.06
.\scripts\push-images.ps1 -Registry registry.example.com -Repository platform -Tag 2026.06
```

推送后，替换 `deploy/k8s/backend.yaml` 和 `deploy/k8s/frontend.yaml` 中的 `image`，或在 Docker Compose 中设置 `DPF_BACKEND_IMAGE` 和 `DPF_FRONTEND_IMAGE`。

也可以生成部署镜像配置文件：

```bash
scripts/render-deploy-images.sh --registry registry.example.com --repository platform --tag 2026.06 --database-url postgresql://factory:replace-with-password@postgres.example.com:5432/deployment_package_factory --storage-class nfs-rwx
```

Windows PowerShell：

```powershell
.\scripts\render-deploy-images.ps1 -Registry registry.example.com -Repository platform -Tag 2026.06 -DatabaseUrl postgresql://factory:replace-with-password@postgres.example.com:5432/deployment_package_factory -StorageClass nfs-rwx
```

默认会生成：

```text
deploy/generated/factory.env
deploy/generated/kustomization.yaml
deploy/generated/pvc-storage-class-patch.yaml
```

## Docker Compose

```bash
scripts/validate-deploy-config.sh docker-compose
docker compose --env-file deploy/generated/factory.env -f deploy/docker-compose.prod.yml up -d
```

可选环境变量：

```bash
export DPF_BACKEND_IMAGE=registry.example.com/platform/deployment-package-factory-backend:2026.06
export DPF_WORKER_IMAGE=registry.example.com/platform/deployment-package-factory-worker:2026.06
export DPF_FRONTEND_IMAGE=registry.example.com/platform/deployment-package-factory-frontend:2026.06
export DPF_HTTP_PORT=5186
export DEPLOYMENT_PACKAGE_DATABASE_URL=postgresql://factory:replace-with-password@postgres.example.com:5432/deployment_package_factory
export DEPLOYMENT_PACKAGE_API_TOKEN=replace-with-strong-random-token
export DEPLOYMENT_PACKAGE_FRONTEND_API_BASE_URL=
export DEPLOYMENT_PACKAGE_FRONTEND_API_TOKEN=replace-with-strong-random-token
export DEPLOYMENT_PACKAGE_MAX_CONCURRENT_BUILDS=1
export DEPLOYMENT_PACKAGE_WORKER_POLL_INTERVAL_SECONDS=3
export DEPLOYMENT_PACKAGE_WORKER_HEARTBEAT_SECONDS=15
export DEPLOYMENT_PACKAGE_RUNNING_TASK_TIMEOUT_MINUTES=120
export DEPLOYMENT_PACKAGE_RETENTION_DAYS=30
export DEPLOYMENT_PACKAGE_MAX_TOTAL_GB=500
```

访问：

```text
http://localhost:5186
```

数据会写入 Docker volume `deployment-package-data`。

## Kubernetes

### 来源环境 namespace 结构

导包工具自身部署在 `deployment-package-factory` namespace；被导出的 dev/test 业务来源环境需要先按标准结构创建 namespace：

```text
{env}-middleware-public
{env}-base-public
{env}-biz-{product}-{profile}
```

当前内置结构在 `deploy/source-environments/source-environments.yaml` 中维护，包含：

```text
dev-middleware-public / dev-base-public / dev-biz-eam-4x60 / dev-biz-mes-4x60 / dev-biz-mes-4x3
test-middleware-public / test-base-public / test-biz-eam-4x60 / test-biz-mes-4x60 / test-biz-mes-4x3
```

渲染并安装：

```bash
scripts/render-source-environments.sh
scripts/install-source-environments.sh
```

Windows PowerShell：

```powershell
.\scripts\render-source-environments.ps1
.\scripts\install-source-environments.ps1
```

这一步只创建并标记 namespace，后续 Pod/容器分类器会基于 `local-ai.io/environment`、`local-ai.io/layer`、`local-ai.io/product`、`local-ai.io/profile` 等标签识别 middleware、base platform、business、support 和 unknown。

部署：

```bash
scripts/validate-deploy-config.sh k8s
kubectl apply -k deploy/generated
```

Windows PowerShell：

```powershell
.\scripts\validate-deploy-config.ps1 -Mode k8s
kubectl apply -k deploy/generated
```

部署后检查：

```bash
kubectl get pods -n deployment-package-factory
kubectl get ingress -n deployment-package-factory
```

默认域名：

```text
deployment-package-factory.example.com
```

生产使用前需要调整：

- `deploy/k8s/ingress.yaml` 中的域名。
- `scripts/render-deploy-images.*` 生成的镜像地址。
- `deploy/k8s/pvc.yaml` 中的存储大小。backend 负责下载，worker 负责生成，两者必须能同时访问同一个产物卷；推荐 NFS、CephFS 或云厂商文件存储类 StorageClass。实际 RWX StorageClass 通过 `scripts/render-deploy-images.* --storage-class/-StorageClass` 生成到 `deploy/generated/pvc-storage-class-patch.yaml`。
- `deploy/k8s/configmap.yaml` 中的并发数、保留天数和容量上限。
- 复制 `deploy/k8s/secret.template.yaml` 为 `deploy/k8s/secret.yaml`，替换 `DEPLOYMENT_PACKAGE_DATABASE_URL`、`DEPLOYMENT_PACKAGE_API_TOKEN` 和 `DEPLOYMENT_PACKAGE_FRONTEND_API_TOKEN`。`deploy/k8s/secret.yaml` 已被 `.gitignore` 忽略，并会随 `kubectl apply -k deploy/generated` 一起部署。K8s/生产部署必须使用外部 PostgreSQL 等生产关系库保存任务和审计元数据。
- `deploy/k8s/networkpolicy.yaml` 默认只开放前端、后端、DNS、镜像/HTTP 出口和 PostgreSQL 出口；如果外部数据库、镜像仓库或对象存储使用了其他端口，需要按集群网络策略扩展。

前端镜像启动时会根据 `DEPLOYMENT_PACKAGE_FRONTEND_API_BASE_URL` 和 `DEPLOYMENT_PACKAGE_FRONTEND_API_TOKEN` 生成 `/runtime-config.js`，因此同一个前端镜像可以复用于 dev、test、prod；受保护环境下前端 token 应与后端 API token 保持一致。后续接入 IAM/OIDC 后可改为登录态令牌。

默认 K8s/生产 Compose 部署采用 worker 模式：API 只创建任务，`deployment-package-factory-worker` 负责领取和执行任务。本地开发 `docker-compose.yml` 仍保留后台任务模式，便于单进程调试。
如果 worker 进程崩溃，后续 worker 会根据任务的 `heartbeatAt` 判断是否超过 `DEPLOYMENT_PACKAGE_RUNNING_TASK_TIMEOUT_MINUTES`，超时的 running 任务会被标记为 failed，用户可在页面上重试。执行中的 worker 会按 `DEPLOYMENT_PACKAGE_WORKER_HEARTBEAT_SECONDS` 周期刷新心跳。

## Worker 独立部署

### Worker 架构说明

Worker 进程是独立的后台任务执行器，与 API 服务解耦：

- **API 服务**（backend）：接收用户请求，创建任务并持久化到数据库，返回任务 ID
- **Worker 进程**（worker）：轮询数据库，领取 pending 任务，执行构建，更新任务状态

两者通过 **PostgreSQL 数据库** 协调，使用 `SELECT FOR UPDATE SKIP LOCKED` 实现分布式锁，避免同一任务被多个 Worker 抢占。

### Worker 环境变量

Worker 进程支持以下关键环境变量（已在 `deploy/k8s/configmap.yaml` 中配置）：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DEPLOYMENT_PACKAGE_EXECUTION_MODE` | `background` | **必须设置为 `worker`** 才能启用 Worker 模式 |
| `DEPLOYMENT_PACKAGE_DATABASE_URL` | 无 | **必填**，PostgreSQL 连接字符串 |
| `DEPLOYMENT_PACKAGE_OUTPUT_DIR` | `/app/data/deployment-packages` | 部署包产物输出目录 |
| `DEPLOYMENT_PACKAGE_MAX_CONCURRENT_BUILDS` | `1` | 单个 Worker 进程内最大并发构建数 |
| `DEPLOYMENT_PACKAGE_WORKER_POLL_INTERVAL_SECONDS` | `3` | 轮询 pending 任务的间隔（秒） |
| `DEPLOYMENT_PACKAGE_WORKER_HEARTBEAT_SECONDS` | `15` | 心跳刷新间隔（秒） |
| `DEPLOYMENT_PACKAGE_RUNNING_TASK_TIMEOUT_MINUTES` | `120` | 任务超时阈值（分钟） |
| `DEPLOYMENT_PACKAGE_WORKER_ID` | `{hostname}-{random}` | 可选，Worker 实例标识 |

**注意**：
- `DEPLOYMENT_PACKAGE_EXECUTION_MODE` 在 ConfigMap 中统一设置为 `worker`
- Worker Deployment 通过环境变量 `DEPLOYMENT_PACKAGE_EXECUTION_MODE=worker` 显式指定（优先级最高）
- API backend 可保持 `background` 模式或同样设置为 `worker`（当 `worker` 模式时 API 不执行任务）

### 多 Worker 实例部署

Worker 支持水平扩展，多个 Worker 实例可以并行处理不同的任务：

```yaml
spec:
  replicas: 3  # 同时运行 3 个 Worker 实例
```

**数据库层面的并发保护**：
- `PostgresPackageTaskRepository.claim_next_pending()` 使用 `SELECT FOR UPDATE SKIP LOCKED`
- 被某个 Worker 锁定的任务行对其他 Worker 不可见
- 每个 Worker 实例有独立的 `worker_id`（主机名 + 随机后缀）
- 任务的 `worker_id`、`claimed_at`、`heartbeat_at` 字段记录归属和活跃状态

**并发控制**：
- 单个 Worker 进程内的并发由 `MAX_CONCURRENT_BUILDS` 控制（通过 asyncio.Semaphore）
- 集群总并发 = Worker 实例数 × 每实例并发数
- 示例：3 个 Worker × 并发 2 = 最多同时构建 6 个部署包

### Worker 健康检查

验证 Worker 正在运行：

```bash
# 查看 Worker Pod 状态
kubectl get pods -n deployment-package-factory -l app.kubernetes.io/component=worker

# 查看 Worker 日志
kubectl logs -n deployment-package-factory -l app.kubernetes.io/component=worker --tail=50 -f

# 查看 Worker 是否在处理任务（日志中应包含 "Running deployment package task task-xxx"）
kubectl logs -n deployment-package-factory deployment/deployment-package-factory-worker | grep "Running deployment package task"
```

验证 Worker 心跳正常：

```sql
-- 连接到 PostgreSQL
SELECT task_id, status, worker_id, heartbeat_at, updated_at 
FROM package_tasks 
WHERE status = 'running' 
ORDER BY heartbeat_at DESC;
```

如果 `heartbeat_at` 持续更新（每 15 秒刷新一次），说明 Worker 正常工作。

### Worker 故障恢复

**场景 1：Worker 进程崩溃**

- 正在执行的任务会因为心跳超时被标记为 `failed`
- 超时判定：`heartbeat_at` 超过 `DEPLOYMENT_PACKAGE_RUNNING_TASK_TIMEOUT_MINUTES`（默认 120 分钟）
- 其他 Worker 实例会继续处理新任务
- 用户可在前端重试失败的任务

**场景 2：Worker Pod 重启**

- K8s 会自动重启 Worker Pod
- 新 Worker 实例会领取新的 pending 任务
- 旧 Worker 正在处理的任务会因心跳超时被标记为 `failed`

**场景 3：数据库连接丢失**

- Worker 会在下次轮询时尝试重连
- 如果长时间无法连接，Worker 会退出（由 K8s 重启）

### Worker 构建镜像

Worker 使用独立的 Dockerfile：

```bash
# 构建 Worker 镜像
docker build -f backend/Dockerfile.worker -t deployment-package-factory-worker:latest .

# 或使用统一构建脚本
scripts/build-images.sh --tag latest
```

Worker 镜像与 backend 镜像的唯一区别是 `CMD` 命令：
- **backend**: `uvicorn deployment_package_factory.main:app --host 0.0.0.0 --port 8096`
- **worker**: `python -m deployment_package_factory.worker`

两者共享相同的依赖（包括 skopeo），确保镜像导出功能可用。

### 验证 Worker 部署

完整验证流程：

```bash
# 1. 确认 Worker Pod 运行
kubectl get pods -n deployment-package-factory -l app.kubernetes.io/component=worker

# 2. 通过 API 创建一个部署包任务
curl -X POST http://deployment-package-factory.example.com/api/deployment-packages \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "projectKey": "standard-eam",
    "sourceEnv": "test",
    "deployModes": ["k8s"],
    "platformServices": ["iam", "gateway-frontend", "audit"],
    "businessServices": [{"name": "eam", "profile": "4x60"}],
    "database": "postgres",
    "imageMode": "image-manifest"
  }'

# 3. 观察 Worker 日志，应看到 "Running deployment package task task-xxx"
kubectl logs -n deployment-package-factory deployment/deployment-package-factory-worker --tail=100 -f

# 4. 查询任务状态，验证任务从 pending → running → completed
curl http://deployment-package-factory.example.com/api/deployment-packages/tasks/${TASK_ID} \
  -H "Authorization: Bearer ${API_TOKEN}"

# 5. 检查任务的 worker_id 字段，确认是 Worker 而非 API 执行的
# worker_id 格式：{hostname}-{random}，例如 "deployment-package-factory-worker-7d8f9c5b4-abc12-a1b2c3d4"
```

### 故障排查

**问题：Worker 无法领取任务**

检查点：
1. 确认 `DEPLOYMENT_PACKAGE_EXECUTION_MODE=worker` 已设置
2. 确认 `DEPLOYMENT_PACKAGE_DATABASE_URL` 配置正确
3. 查看 Worker 日志是否有数据库连接错误
4. 确认 API 服务正常创建任务（任务状态为 `pending`）

**问题：任务一直处于 pending 状态**

检查点：
1. Worker Pod 是否正在运行：`kubectl get pods -n deployment-package-factory`
2. Worker 日志是否有错误：`kubectl logs -n deployment-package-factory deployment/deployment-package-factory-worker`
3. 数据库中是否有 pending 任务：`SELECT * FROM package_tasks WHERE status = 'pending'`

**问题：任务频繁超时失败**

检查点：
1. 提高 `DEPLOYMENT_PACKAGE_RUNNING_TASK_TIMEOUT_MINUTES`（当前 120 分钟）
2. 检查镜像导出是否因网络问题耗时过长
3. 考虑增加 Worker 资源限制（CPU/Memory）

## 监控指标

后端服务提供 Prometheus 文本指标：

```text
GET /metrics
```

`deploy/k8s/backend.yaml` 中的 Service 已配置：

```yaml
prometheus.io/scrape: "true"
prometheus.io/path: /metrics
prometheus.io/port: "8096"
```

如果集群使用 Prometheus Operator，建议后续按平台规范补充 `ServiceMonitor`；当前 annotation 可兼容基础的 Prometheus 自动发现配置。

## 数据与权限

后端需要持久化以下内容：

```text
/app/data/deployment-packages/
```

K8s 生产部署中，任务和审计元数据通过 `DEPLOYMENT_PACKAGE_DATABASE_URL` 写入外部 PostgreSQL。PVC 只用于保存生成中的工作目录和最终 tar.gz 产物：

```text
/app/data/deployment-packages/
  work/
  artifacts/
```

`deploy/k8s/pvc.yaml` 默认使用 `ReadWriteMany`，并保留 `__REPLACE_WITH_RWX_STORAGE_CLASS__` 作为模板占位符；生产部署前必须通过 `scripts/render-deploy-images.* --storage-class/-StorageClass` 生成 `deploy/generated/pvc-storage-class-patch.yaml`，由 Kustomize 注入集群可用的共享文件存储类。不要在多节点 K8s 生产环境使用 `ReadWriteOnce`，否则 worker 生成的包可能无法被 backend Pod 下载。

如果启用镜像归档导出，backend/worker Pod 需要能访问来源镜像仓库。默认 backend 和 worker 镜像内置 `skopeo`，通过 daemonless 方式检查环境并生成 `docker load` 可导入的镜像 tar，不需要挂载宿主机 Docker socket。Docker Compose 部署如未使用带 `skopeo` 的镜像，可回退到 Docker CLI，但需要自行提供 Docker daemon 访问能力。
