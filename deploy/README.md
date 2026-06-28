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
scripts/render-deploy-images.sh --registry registry.example.com --repository platform --tag 2026.06
```

Windows PowerShell：

```powershell
.\scripts\render-deploy-images.ps1 -Registry registry.example.com -Repository platform -Tag 2026.06
```

默认会生成：

```text
deploy/generated/factory.env
deploy/generated/kustomization.yaml
```

## Docker Compose

```bash
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

部署：

```bash
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
- `deploy/k8s/pvc.yaml` 中的存储大小和 StorageClass。
- `deploy/k8s/configmap.yaml` 中的并发数、保留天数和容量上限。
- 复制 `deploy/k8s/secret.template.yaml` 为 `deploy/k8s/secret.yaml`，替换 `DEPLOYMENT_PACKAGE_DATABASE_URL`、`DEPLOYMENT_PACKAGE_API_TOKEN` 和 `DEPLOYMENT_PACKAGE_FRONTEND_API_TOKEN` 后执行 `kubectl apply -f deploy/k8s/secret.yaml`。K8s/生产部署必须使用外部 PostgreSQL 等生产关系库保存任务和审计元数据。

前端镜像启动时会根据 `DEPLOYMENT_PACKAGE_FRONTEND_API_BASE_URL` 和 `DEPLOYMENT_PACKAGE_FRONTEND_API_TOKEN` 生成 `/runtime-config.js`，因此同一个前端镜像可以复用于 dev、test、prod；受保护环境下前端 token 应与后端 API token 保持一致。后续接入 IAM/OIDC 后可改为登录态令牌。

默认 K8s/生产 Compose 部署采用 worker 模式：API 只创建任务，`deployment-package-factory-worker` 负责领取和执行任务。本地开发 `docker-compose.yml` 仍保留后台任务模式，便于单进程调试。
如果 worker 进程崩溃，后续 worker 会根据任务的 `heartbeatAt` 判断是否超过 `DEPLOYMENT_PACKAGE_RUNNING_TASK_TIMEOUT_MINUTES`，超时的 running 任务会被标记为 failed，用户可在页面上重试。执行中的 worker 会按 `DEPLOYMENT_PACKAGE_WORKER_HEARTBEAT_SECONDS` 周期刷新心跳。

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

K8s 生产部署中，任务和审计元数据不写 SQLite 文件，而是通过 `DEPLOYMENT_PACKAGE_DATABASE_URL` 写入外部 PostgreSQL。PVC 只用于保存生成中的工作目录和最终 tar.gz 产物：

```text
/app/data/deployment-packages/
```

如果启用镜像归档导出，backend/worker Pod 需要能访问来源镜像仓库。默认 backend 和 worker 镜像内置 `skopeo`，通过 daemonless 方式检查环境并生成 `docker load` 可导入的镜像 tar，不需要挂载宿主机 Docker socket。Docker Compose 部署如未使用带 `skopeo` 的镜像，可回退到 Docker CLI，但需要自行提供 Docker daemon 访问能力。
