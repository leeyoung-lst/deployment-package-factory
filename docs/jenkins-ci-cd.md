# Jenkins CI/CD 配置

本项目使用根目录 `Jenkinsfile` 构建“部署包工厂”自身，并可选择推送镜像、渲染 K8s 配置、部署到 K8s。

## Jenkins Agent 要求

- Linux agent。
- 已安装 `python`、`node`、`corepack`、`docker`、`kubectl`。
- Jenkins 用户可执行 Docker build/push。
- 如启用 `DEPLOY_TO_K8S`，agent 能访问目标 K8s API。

## 必需凭据

在 Jenkins Credentials 中创建：

| ID | 类型 | 用途 |
| --- | --- | --- |
| `dpf-registry-credentials` | Username with password | Docker registry 登录。仅 `PUSH_IMAGES=true` 时使用。 |
| `dpf-api-token` | Secret text | 后端 API token，同时写入前端运行时配置。 |
| `dpf-database-url` | Secret text | 生产 PostgreSQL 连接串。 |
| `dpf-kubeconfig` | Secret file | 目标 K8s kubeconfig。仅 `DEPLOY_TO_K8S=true` 时使用。 |

## Pipeline 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `REGISTRY` | `registry.example.com` | 镜像仓库地址。 |
| `REPOSITORY` | `platform` | 仓库命名空间。 |
| `IMAGE_TAG` | 空 | 为空时使用 `branch-buildNumber`。 |
| `STORAGE_CLASS` | `nfs-rwx` | K8s 产物 PVC 的 RWX StorageClass。 |
| `HTTP_PORT` | `5186` | 生成 Compose env 时使用的前端端口。 |
| `PUSH_IMAGES` | `true` | 是否推送三类镜像。 |
| `DEPLOY_TO_K8S` | `false` | 是否执行 `kubectl apply -k deploy/generated`。 |
| `NO_CACHE` | `false` | Docker 构建是否禁用缓存。 |

## 执行阶段

1. `Prepare`：检查工具链，计算镜像 tag。
2. `Backend Tests`：运行 `python -m pytest backend/tests -q`。
3. `Frontend Build`：使用 `pnpm@10.24.0` 和 lockfile 构建前端。
4. `Validate Manifests`：校验 K8s YAML 与 `git diff --check`。
5. `Build Images`：调用 `scripts/build-images.sh` 构建 backend、worker、frontend。
6. `Push Images`：可选推送镜像。
7. `Render Deploy Config`：生成 `deploy/generated/` 与被忽略的 `deploy/k8s/secret.yaml`。
8. `Deploy to K8s`：可选部署并等待 rollout。

流水线结束时会删除 `deploy/generated/factory.env`、`deploy/k8s/secret.yaml` 和临时渲染文件，避免数据库连接串或 API token 被归档。Jenkins 只归档 `deploy/generated/kustomization.yaml` 与 `deploy/generated/pvc-storage-class-patch.yaml` 作为可审计的部署配置摘要。

## 推荐作业

建议建两个 Jenkins 作业：

- `deployment-package-factory-ci`：`PUSH_IMAGES=false`、`DEPLOY_TO_K8S=false`，用于 MR/PR。
- `deployment-package-factory-deploy-test`：`PUSH_IMAGES=true`、`DEPLOY_TO_K8S=true`，用于测试环境部署。

生产环境建议保留人工确认步骤，或在 Jenkins 上将 `DEPLOY_TO_K8S` 限制为受保护分支可用。
