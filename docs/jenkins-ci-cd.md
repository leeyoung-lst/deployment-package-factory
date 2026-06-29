# Jenkins CI/CD 配置

本项目使用根目录 `Jenkinsfile` 构建“部署包工厂”自身，并可选择推送镜像、渲染 K8s 配置、部署到 K8s。

## Jenkins Agent 要求

- Linux agent。
- 已安装 `docker`、`kubectl`、`git`。
- Jenkins 用户可执行 Docker build/push。
- 如启用 `DEPLOY_TO_K8S`，agent 能访问目标 K8s API。
- 当前测试环境 Jenkins 节点使用 `/opt/jenkins/kube/config` 访问 K8s；K8s 可视化入口为 `https://headlamp.local/`，hosts 需指向 `192.168.10.220`。

## 必需凭据

在 Jenkins Credentials 中创建：

| ID | 类型 | 用途 |
| --- | --- | --- |
| `harbor-admin` | Username with password | Docker registry 登录。仅 `PUSH_IMAGES=true` 时使用。 |
| `github-token` | Username with password | Jenkins 从独立 Git 仓库拉取源码。 |
| `dpf-api-token` | Secret text | 后端 API token，同时写入前端运行时配置。 |
| `dpf-database-url` | Secret text | 生产 PostgreSQL 连接串。 |

## Pipeline 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `REGISTRY` | `192.168.10.210` | 镜像仓库地址。 |
| `REPOSITORY` | `local-ai` | 仓库命名空间。 |
| `IMAGE_TAG` | 空 | 为空时使用当前 Git commit SHA。 |
| `STORAGE_CLASS` | `nfs-client` | K8s 产物 PVC 的 RWX StorageClass。 |
| `KUBECONFIG_PATH` | `/opt/jenkins/kube/config` | Jenkins 节点上的 kubeconfig 路径。 |
| `PUSH_IMAGES` | `true` | 是否推送三类镜像。 |
| `DEPLOY_TO_K8S` | `true` | 是否执行 `kubectl apply -k deploy/generated`。 |
| `USE_IN_CLUSTER_POSTGRES` | `true` | 测试环境使用命名空间内 Postgres；生产应改用外部数据库连接串。 |
| `NO_CACHE` | `false` | Docker 构建是否禁用缓存。 |

## 执行阶段

1. `Prepare`：检查 `git`、`docker`、`kubectl`，计算镜像 tag。
2. `Build Images`：调用 `scripts/build-images.sh` 构建 backend、worker、frontend。前后端依赖安装在 Docker build 内完成。
3. `Push Images`：可选推送镜像。
4. `Render Deploy Config`：生成 `deploy/generated/` 与被忽略的 `deploy/k8s/secret.yaml`。
5. `Ensure Test Namespace`：创建 namespace 与 Harbor 拉取 Secret。
6. `Ensure Test Postgres`：测试环境创建命名空间内 Postgres，生产环境建议关闭并改用外部 PostgreSQL。
7. `Deploy to K8s`：可选部署并等待 rollout。
8. `Smoke Test`：等待 backend Deployment rollout 完成，选择一个 Running 且 Ready 的 backend Pod，在 Pod 内验证 `/health`、`/metrics`、`/api/deployment-packages/options`。烟测不按 Pod label 等待全部 Pod Ready，避免滚动更新期间旧 Pod 与新 Pod 同时匹配导致误超时。

流水线结束时会删除 `deploy/generated/factory.env`、`deploy/k8s/secret.yaml` 和临时渲染文件，避免数据库连接串或 API token 被归档。Jenkins 只归档 `deploy/generated/kustomization.yaml` 与 `deploy/generated/pvc-storage-class-patch.yaml` 作为可审计的部署配置摘要。

## 推荐作业

建议建两个 Jenkins 作业：

- `deployment-package-factory-ci`：`PUSH_IMAGES=false`、`DEPLOY_TO_K8S=false`，用于 MR/PR。
- `deployment-package-factory-deploy-test`：`PUSH_IMAGES=true`、`DEPLOY_TO_K8S=true`，用于测试环境部署。

生产环境建议保留人工确认步骤，或在 Jenkins 上将 `DEPLOY_TO_K8S` 限制为受保护分支可用。
