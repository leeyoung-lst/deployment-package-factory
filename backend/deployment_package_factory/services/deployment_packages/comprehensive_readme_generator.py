"""完整的部署文档生成器 - Phase 2.3"""
from __future__ import annotations


def generate_comprehensive_readme(manifest: dict, image_entries: list[dict] | None = None) -> str:
    """
    生成完整的部署文档

    Args:
        manifest: 包清单字典
        image_entries: 镜像条目列表（可选）

    Returns:
        完整的 README.md 内容
    """
    sections = []

    # 标题和概述
    sections.append(_generate_header(manifest))

    # 目录
    sections.append(_generate_table_of_contents())

    # 快速开始
    sections.append(_generate_quick_start(manifest))

    # 部署前准备
    sections.append(_generate_prerequisites(manifest))

    # 架构概览
    sections.append(_generate_architecture_overview(manifest))

    # 服务清单
    sections.append(_generate_services_list(manifest))

    # 详细部署步骤
    sections.append(_generate_deployment_steps(manifest))

    # 初始化配置
    sections.append(_generate_initialization_guide(manifest))

    # 验证和测试
    sections.append(_generate_verification_guide(manifest))

    # 网络拓扑
    sections.append(_generate_network_topology(manifest))

    # 存储规划
    sections.append(_generate_storage_planning(manifest))

    # 常见问题
    sections.append(_generate_faq(manifest))

    # 故障排查
    sections.append(_generate_troubleshooting(manifest))

    # 镜像清单（如果提供）
    if image_entries:
        sections.append(_generate_image_manifest(image_entries))

    # 附录
    sections.append(_generate_appendix(manifest))

    return "\n\n".join(sections)


def _generate_header(manifest: dict) -> str:
    """生成文档头部"""
    package_id = manifest["packageId"]
    project_key = manifest.get("projectKey", "custom")
    product_version = manifest.get("productVersion", "")
    source_env = manifest["sourceEnv"]
    target_env = manifest["targetEnv"]
    deploy_modes = ", ".join(manifest["deployModes"]) or "未指定"
    database = manifest["database"]

    return f"""# Local AI 生产部署包

> 📦 包编号：`{package_id}`
> 🏷️ 项目：`{project_key}`
> 🔖 版本：`{product_version or "未指定"}`
> 🌍 来源环境：`{source_env}` → 目标环境：`{target_env}`
> 🚀 部署方式：{deploy_modes}
> 🗄️ 数据库：`{database}`

本部署包包含了将 Local AI 系统从 {source_env} 环境迁移到 {target_env} 环境所需的全部资源和配置。

⚠️ **重要提示**：部署前请仔细阅读本文档，并完成所有前置准备工作。"""


def _generate_table_of_contents() -> str:
    """生成目录"""
    return """## 📚 目录

- [快速开始](#-快速开始)
- [部署前准备](#-部署前准备)
- [架构概览](#-架构概览)
- [服务清单](#-服务清单)
- [详细部署步骤](#-详细部署步骤)
- [初始化配置](#-初始化配置)
- [验证和测试](#-验证和测试)
- [网络拓扑](#-网络拓扑)
- [存储规划](#-存储规划)
- [常见问题](#-常见问题)
- [故障排查](#-故障排查)
- [附录](#-附录)"""


def _generate_quick_start(manifest: dict) -> str:
    """生成快速开始指南"""
    deploy_modes = manifest["deployModes"]
    has_k8s = "k8s" in deploy_modes
    has_compose = "docker-compose" in deploy_modes

    quick_start = """## 🚀 快速开始

### 最小化部署流程

```bash
# 1. 质量检查（必须通过）
./quality-gate.sh

# 2. 安装部署
"""

    if has_k8s:
        quick_start += """./install.sh --mode k8s
"""
    elif has_compose:
        quick_start += """./install.sh --mode docker-compose
"""

    quick_start += """
# 3. 验证部署
./verify.sh

# 4. 查看服务状态
"""

    if has_k8s:
        quick_start += """kubectl get pods -n local-ai-prod
"""
    elif has_compose:
        quick_start += """docker-compose ps
"""

    quick_start += """```

> 💡 **提示**：首次部署建议使用交互模式：`./install.sh --interactive`"""

    return quick_start


def _generate_prerequisites(manifest: dict) -> str:
    """生成部署前准备"""
    deploy_modes = manifest["deployModes"]
    database = manifest["database"]
    middleware = manifest.get("middleware", [])

    prereq = """## 📋 部署前准备

### 1. 硬件要求

#### 最低配置
- CPU: 8 核
- 内存: 16 GB
- 磁盘: 100 GB SSD
- 网络: 100 Mbps

#### 推荐配置
- CPU: 16 核
- 内存: 32 GB
- 磁盘: 500 GB SSD
- 网络: 1 Gbps

### 2. 软件依赖

"""

    # Kubernetes 依赖
    if "k8s" in deploy_modes:
        prereq += """#### Kubernetes 环境
- Kubernetes 1.20+
- kubectl 客户端
- 集群管理员权限
- Helm 3.0+（可选）

"""

    # Docker Compose 依赖
    if "docker-compose" in deploy_modes:
        prereq += """#### Docker Compose 环境
- Docker 20.10+
- Docker Compose 2.0+
- 至少 20 GB 可用磁盘空间

"""

    # 数据库
    prereq += f"""#### 数据库
- {database.upper()} {"14+" if database == "postgres" else "8+"}
- 数据库管理员权限
- 至少 10 GB 可用空间

"""

    # 中间件
    if middleware:
        prereq += """#### 中间件
"""
        if "minio" in middleware:
            prereq += "- MinIO 服务器（用于对象存储）\n"
        if "qdrant" in middleware:
            prereq += "- Qdrant 服务器（用于向量数据库）\n"
        if "redis" in middleware:
            prereq += "- Redis 6.0+（用于缓存）\n"
        if "camunda" in middleware:
            prereq += "- Camunda 7.x（用于工作流引擎）\n"

    prereq += """
### 3. 网络要求

- 目标服务器可访问镜像仓库
- 内部服务之间网络互通
- 开放必要的端口（详见网络拓扑章节）

### 4. 权限要求

- 操作系统：root 或具有 sudo 权限的用户
- Kubernetes：cluster-admin 角色
- 数据库：数据库管理员权限
- 镜像仓库：读取权限

### 5. 准备清单

在开始部署前，请确认以下清单：

- [ ] 硬件资源满足要求
- [ ] 所有软件依赖已安装
- [ ] 网络连接正常
- [ ] 权限已获取
- [ ] 已备份现有数据（如果是升级）
- [ ] 已阅读本部署文档"""

    return prereq


def _generate_architecture_overview(manifest: dict) -> str:
    """生成架构概览"""
    platform_services = manifest.get("platformServices", [])
    business_services = manifest.get("businessServices", [])
    database = manifest["database"]
    middleware = manifest.get("middleware", [])

    arch = """## 🏗️ 架构概览

### 系统架构

本部署包采用微服务架构，包含以下层次：

```
┌─────────────────────────────────────────────────────┐
│                     前端层                          │
│              (Web UI / Mobile App)                  │
└─────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│                   API 网关层                        │
│          (路由、认证、限流、负载均衡)               │
└─────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│                   业务服务层                        │
│     (微服务：EAM, MES, ERP, APS 等)                │
└─────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│                   平台服务层                        │
│     (IAM, 监控, 日志, 配置管理等)                  │
└─────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│                   数据存储层                        │
│   (数据库, 对象存储, 向量数据库, 缓存)             │
└─────────────────────────────────────────────────────┘
```

### 核心组件

"""

    # 平台服务
    if platform_services:
        arch += f"""#### 平台服务 ({len(platform_services)} 个)
"""
        for service in platform_services:
            arch += f"- `{service}`: {_get_service_description(service)}\n"
        arch += "\n"

    # 业务服务
    if business_services:
        arch += f"""#### 业务服务 ({len(business_services)} 个)
"""
        for service in business_services:
            arch += f"- `{service}`: {_get_service_description(service)}\n"
        arch += "\n"

    # 数据存储
    arch += f"""#### 数据存储
- 主数据库: {database.upper()}
"""
    if "minio" in middleware:
        arch += "- 对象存储: MinIO\n"
    if "qdrant" in middleware:
        arch += "- 向量数据库: Qdrant\n"
    if "redis" in middleware:
        arch += "- 缓存: Redis\n"

    arch += """
### 部署拓扑

根据部署模式，系统拓扑如下：

- **Kubernetes 模式**：使用 Deployment、Service、Ingress 等资源
- **Docker Compose 模式**：使用 Docker 网络和容器编排"""

    return arch


def _generate_services_list(manifest: dict) -> str:
    """生成服务清单"""
    platform_services = manifest.get("platformServices", [])
    business_services = manifest.get("businessServices", [])

    services_list = """## 📦 服务清单

### 平台服务

| 服务名称 | 描述 | 端口 | 依赖 |
|---------|------|------|------|
"""

    for service in platform_services:
        desc = _get_service_description(service)
        port = _get_service_port(service)
        deps = _get_service_dependencies(service)
        services_list += f"| {service} | {desc} | {port} | {deps} |\n"

    if business_services:
        services_list += """
### 业务服务

| 服务名称 | 描述 | 端口 | 依赖 |
|---------|------|------|------|
"""
        for service in business_services:
            desc = _get_service_description(service)
            port = _get_service_port(service)
            deps = _get_service_dependencies(service)
            services_list += f"| {service} | {desc} | {port} | {deps} |\n"

    return services_list


def _generate_deployment_steps(manifest: dict) -> str:
    """生成详细部署步骤"""
    deploy_modes = manifest["deployModes"]

    steps = """## 📝 详细部署步骤

### 步骤 1: 解压部署包

```bash
# 解压部署包
tar -xzf local-ai-prod-package-*.tar.gz
cd local-ai-prod-package-*/
```

### 步骤 2: 运行质量检查

```bash
# 运行质量门禁检查
./quality-gate.sh

# 查看质量报告
cat docs/quality-report.runtime.md
```

⚠️ **重要**：质量检查必须全部通过才能继续部署。

### 步骤 3: 准备环境

"""

    if "k8s" in deploy_modes:
        steps += """#### Kubernetes 环境准备

```bash
# 创建命名空间
kubectl create namespace local-ai-prod

# 配置镜像拉取密钥（如果需要）
kubectl create secret docker-registry registry-secret \\
  --docker-server=your-registry.com \\
  --docker-username=your-username \\
  --docker-password=your-password \\
  -n local-ai-prod

# 应用配置
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
```

"""

    if "docker-compose" in deploy_modes:
        steps += """#### Docker Compose 环境准备

```bash
# 加载镜像（如果使用镜像归档）
./scripts/load-images.sh

# 配置环境变量
cp docker-compose/.env.template docker-compose/.env
# 编辑 .env 文件，填写实际配置
vi docker-compose/.env
```

"""

    steps += """### 步骤 4: 初始化数据库

```bash
# 进入初始化目录
cd init/

# 运行初始化脚本
./run-init.sh

# 验证数据库初始化
psql -U postgres -d local_ai -c "\\dt iam.*"
```

### 步骤 5: 部署服务

"""

    if "k8s" in deploy_modes:
        steps += """#### Kubernetes 部署

```bash
# 使用安装脚本（推荐）
./install.sh --mode k8s --namespace local-ai-prod

# 或手动部署
kubectl apply -f k8s/deployments.yaml
kubectl apply -f k8s/services.yaml
kubectl apply -f k8s/ingress.yaml
```

"""

    if "docker-compose" in deploy_modes:
        steps += """#### Docker Compose 部署

```bash
# 使用安装脚本（推荐）
./install.sh --mode docker-compose

# 或手动部署
cd docker-compose/
docker-compose up -d
```

"""

    steps += """### 步骤 6: 验证部署

```bash
# 运行验证脚本
./verify.sh

# 查看验证报告
cat docs/verification-report.md
```

### 步骤 7: 访问系统

根据部署模式访问系统：

"""

    if "k8s" in deploy_modes:
        steps += """- **Kubernetes**: 通过 Ingress 域名访问
  ```bash
  kubectl get ingress -n local-ai-prod
  ```
"""

    if "docker-compose" in deploy_modes:
        steps += """- **Docker Compose**: 访问 http://localhost:80
  ```bash
  docker-compose ps
  ```
"""

    return steps


def _generate_initialization_guide(manifest: dict) -> str:
    """生成初始化配置指南"""
    database = manifest["database"]
    middleware = manifest.get("middleware", [])

    init_guide = f"""## ⚙️ 初始化配置

### 数据库初始化

本部署包包含完整的数据库初始化脚本，位于 `init/{database}/` 目录。

#### 初始化内容

1. **Schema 创建**：创建所有必需的数据库 schema
2. **表结构**：创建所有表、索引、约束
3. **默认数据**：插入默认管理员用户和配置数据
4. **函数和触发器**：创建必要的数据库函数

#### 执行初始化

```bash
cd init/
./run-init.sh
```

#### 默认管理员账户

⚠️ **安全提示**：首次登录后请立即修改默认密码！

- 用户名: `admin`
- 密码: `Admin@123`
- 邮箱: `admin@example.com`

修改密码：

```sql
UPDATE iam.users
SET password_hash = '$2b$12$<your-new-password-hash>'
WHERE username = 'admin';
```

"""

    # MinIO 初始化
    if "minio" in middleware:
        init_guide += """### MinIO 对象存储初始化

```bash
# 运行 MinIO 初始化脚本
./init/minio/create-buckets.sh

# 验证 bucket 创建
mc ls myminio/
```

创建的 buckets：
- `documents`: 文档存储
- `avatars`: 用户头像
- `logs`: 日志文件
- `backups`: 备份文件

"""

    # Qdrant 初始化
    if "qdrant" in middleware:
        init_guide += """### Qdrant 向量数据库初始化

```bash
# 运行 Qdrant 初始化脚本
./init/qdrant/create-collections.sh

# 验证 collection 创建
curl http://localhost:6333/collections
```

创建的 collections：
- `knowledge-base`: 知识库向量
- `embeddings`: 文本嵌入

"""

    return init_guide


def _generate_verification_guide(manifest: dict) -> str:
    """生成验证和测试指南"""
    deploy_modes = manifest["deployModes"]

    verify = """## ✅ 验证和测试

### 自动验证

```bash
# 运行完整验证
./verify.sh

# 查看验证报告
cat docs/verification-report.md
```

### 手动验证清单

"""

    if "k8s" in deploy_modes:
        verify += """#### Kubernetes 验证

```bash
# 1. 检查 Pod 状态
kubectl get pods -n local-ai-prod
# 所有 Pod 应为 Running 状态

# 2. 检查 Service
kubectl get svc -n local-ai-prod

# 3. 检查 Ingress
kubectl get ingress -n local-ai-prod

# 4. 查看日志
kubectl logs -n local-ai-prod <pod-name>

# 5. 检查资源使用
kubectl top pods -n local-ai-prod
```

"""

    if "docker-compose" in deploy_modes:
        verify += """#### Docker Compose 验证

```bash
# 1. 检查容器状态
docker-compose ps
# 所有容器应为 Up 状态

# 2. 检查日志
docker-compose logs

# 3. 检查网络
docker network ls
docker network inspect <network-name>

# 4. 检查卷
docker volume ls
```

"""

    verify += """### 健康检查

```bash
# API 健康检查
curl http://localhost/api/health

# 数据库连接检查
psql -U postgres -d local_ai -c "SELECT 1;"

# 服务间通信检查
curl http://localhost/api/ping
```

### 功能测试

1. **登录测试**：使用默认管理员账户登录
2. **API 测试**：调用核心 API 接口
3. **数据库测试**：查询关键表
4. **存储测试**：上传/下载文件（如果使用 MinIO）
5. **性能测试**：运行基准测试

"""

    return verify


def _generate_network_topology(manifest: dict) -> str:
    """生成网络拓扑说明"""
    deploy_modes = manifest["deployModes"]

    network = """## 🌐 网络拓扑

### 端口映射

| 服务 | 内部端口 | 外部端口 | 协议 | 说明 |
|------|---------|---------|------|------|
| Web UI | 80 | 80 | HTTP | Web 界面 |
| API Gateway | 8080 | 8080 | HTTP | API 网关 |
| Database | 5432 | 5432 | TCP | PostgreSQL |
| MinIO | 9000 | 9000 | HTTP | 对象存储 |
| Qdrant | 6333 | 6333 | HTTP | 向量数据库 |
| Redis | 6379 | 6379 | TCP | 缓存 |

"""

    if "k8s" in deploy_modes:
        network += """### Kubernetes 网络

```
Internet
    ▼
[Ingress Controller]
    ▼
[Ingress Rules] → 路由规则
    ▼
[Services] → ClusterIP/NodePort
    ▼
[Pods] → 容器
```

**网络策略**：
- 默认拒绝所有入站流量
- 仅允许必要的服务间通信
- Egress 流量受限

"""

    if "docker-compose" in deploy_modes:
        network += """### Docker Compose 网络

```
Host Network
    ▼
[Docker Bridge Network]
    ▼
[Containers] → 容器间通信
```

**网络配置**：
- 所有容器在同一 bridge 网络
- 容器通过服务名互相访问
- 端口映射到主机

"""

    network += """### 防火墙规则

需要开放的端口：

```bash
# Web 访问
firewall-cmd --add-port=80/tcp --permanent
firewall-cmd --add-port=443/tcp --permanent

# API 访问
firewall-cmd --add-port=8080/tcp --permanent

# 数据库访问（仅内部）
firewall-cmd --add-port=5432/tcp --permanent --zone=internal

# 重新加载防火墙
firewall-cmd --reload
```

"""

    return network


def _generate_storage_planning(manifest: dict) -> str:
    """生成存储规划"""
    database = manifest["database"]

    storage = f"""## 💾 存储规划

### 存储需求预估

| 组件 | 最小 | 推荐 | 说明 |
|------|------|------|------|
| 数据库 | 10 GB | 50 GB | {database.upper()} 数据 |
| 对象存储 | 20 GB | 200 GB | 文档、日志等 |
| 日志 | 5 GB | 20 GB | 应用日志 |
| 备份 | 20 GB | 100 GB | 数据库备份 |
| **总计** | **55 GB** | **370 GB** | - |

### 存储位置

#### 数据库
- 路径: `/var/lib/postgresql/data`
- 建议: 使用 SSD，并配置 RAID 10

#### 对象存储 (MinIO)
- 路径: `/data/minio`
- 建议: 使用大容量 HDD，配置 RAID 6

#### 日志
- 路径: `/var/log/local-ai`
- 建议: 定期归档和清理

#### 备份
- 路径: `/backup/local-ai`
- 建议: 使用网络存储或对象存储

### 存储优化建议

1. **数据库**：
   - 启用自动清理（VACUUM）
   - 定期重建索引
   - 分区大表

2. **对象存储**：
   - 启用生命周期策略
   - 冷数据迁移到归档存储
   - 启用压缩

3. **日志**：
   - 使用日志轮转（logrotate）
   - 保留最近 30 天日志
   - 归档旧日志到对象存储

"""

    return storage


def _generate_faq(manifest: dict) -> str:
    """生成常见问题"""
    return """## ❓ 常见问题

### Q1: 部署需要多长时间？

**A**: 根据网络速度和硬件配置，通常需要 15-30 分钟。

### Q2: 可以在生产环境直接部署吗？

**A**: 可以，但建议先在测试环境验证。确保已完成质量检查和风险评估。

### Q3: 如何回滚到之前的版本？

**A**: 保留旧版本的部署包，使用相同的流程部署旧版本即可。数据库需要单独回滚。

### Q4: 支持增量更新吗？

**A**: 目前不支持增量更新，每次部署都是完整替换。

### Q5: 数据库迁移会丢失数据吗？

**A**: 不会。初始化脚本是幂等的，可以重复执行。但建议在迁移前备份数据。

### Q6: 默认管理员密码是什么？

**A**: 用户名 `admin`，密码 `Admin@123`。**请务必在首次登录后修改密码**。

### Q7: 如何配置高可用？

**A**: 需要部署多个副本，并配置负载均衡和故障转移。详见高可用部署文档。

### Q8: 支持哪些数据库？

**A**: 目前支持 PostgreSQL 和达梦数据库（DM8）。

### Q9: 镜像拉取失败怎么办？

**A**: 检查网络连接和镜像仓库权限。可以使用 `./scripts/load-images.sh` 从归档加载镜像。

### Q10: 如何监控系统运行状态？

**A**: 系统内置监控端点，可以使用 Prometheus + Grafana 进行监控。

"""


def _generate_troubleshooting(manifest: dict) -> str:
    """生成故障排查指南"""
    deploy_modes = manifest["deployModes"]

    troubleshooting = """## 🔧 故障排查

### 部署失败

#### 症状：质量检查失败

**可能原因**：
- 文件缺失或损坏
- 校验和不匹配
- 权限不足

**解决方案**：
```bash
# 重新下载部署包
# 验证文件完整性
sha256sum -c security/SHA256SUMS

# 检查权限
ls -la
```

#### 症状：数据库初始化失败

**可能原因**：
- 数据库连接失败
- 权限不足
- Schema 冲突

**解决方案**：
```bash
# 检查数据库连接
psql -U postgres -c "SELECT 1;"

# 检查权限
psql -U postgres -c "\\du"

# 清理并重试
psql -U postgres -c "DROP SCHEMA IF EXISTS iam CASCADE;"
./init/run-init.sh
```

"""

    if "k8s" in deploy_modes:
        troubleshooting += """#### 症状：Pod 无法启动

**可能原因**：
- 镜像拉取失败
- 资源不足
- 配置错误

**解决方案**：
```bash
# 查看 Pod 状态
kubectl describe pod <pod-name> -n local-ai-prod

# 查看日志
kubectl logs <pod-name> -n local-ai-prod

# 检查事件
kubectl get events -n local-ai-prod --sort-by='.lastTimestamp'
```

"""

    if "docker-compose" in deploy_modes:
        troubleshooting += """#### 症状：容器无法启动

**可能原因**：
- 端口冲突
- 卷挂载失败
- 环境变量未配置

**解决方案**：
```bash
# 查看容器日志
docker-compose logs <service-name>

# 检查端口占用
netstat -tunlp | grep <port>

# 检查卷
docker volume ls
docker volume inspect <volume-name>
```

"""

    troubleshooting += """### 运行时问题

#### 症状：服务响应慢

**可能原因**：
- 资源不足
- 数据库查询慢
- 网络延迟

**解决方案**：
```bash
# 检查资源使用
top
df -h
free -m

# 检查数据库慢查询
psql -U postgres -d local_ai -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# 检查网络
ping <service-host>
curl -w "@curl-format.txt" -o /dev/null -s <api-url>
```

#### 症状：无法登录

**可能原因**：
- 数据库未初始化
- 配置错误
- 密码错误

**解决方案**：
```bash
# 检查用户表
psql -U postgres -d local_ai -c "SELECT * FROM iam.users WHERE username = 'admin';"

# 重置管理员密码
psql -U postgres -d local_ai -c "UPDATE iam.users SET password_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLaEgj5u' WHERE username = 'admin';"
```

### 获取帮助

如果以上方法无法解决问题，请联系技术支持：

1. 收集日志：`./scripts/collect-logs.sh`
2. 生成诊断报告：`./scripts/diagnose.sh`
3. 联系技术支持，提供诊断报告

"""

    return troubleshooting


def _generate_image_manifest(image_entries: list[dict]) -> str:
    """生成镜像清单"""
    total_size = sum(entry.get("size", 0) for entry in image_entries if entry.get("size"))

    manifest = f"""## 📦 镜像清单

本部署包包含 {len(image_entries)} 个容器镜像。

### 镜像统计

- 总镜像数: {len(image_entries)}
- 总大小: {_format_bytes(total_size)}

### 镜像列表

| 镜像名称 | 标签 | 大小 | 架构 |
|---------|------|------|------|
"""

    for entry in image_entries[:20]:  # 只显示前20个
        ref = entry.get("targetRef", entry.get("sourceRef", ""))
        if ":" in ref:
            name, tag = ref.rsplit(":", 1)
        else:
            name, tag = ref, "latest"

        size = entry.get("size", 0)
        arch = entry.get("architecture", "amd64")

        manifest += f"| {name} | {tag} | {_format_bytes(size)} | {arch} |\n"

    if len(image_entries) > 20:
        manifest += f"\n... 还有 {len(image_entries) - 20} 个镜像（详见 `images/images.txt`）\n"

    return manifest


def _generate_appendix(manifest: dict) -> str:
    """生成附录"""
    return """## 📚 附录

### A. 文件结构

```
local-ai-prod-package-*/
├── README.md                    # 本文档
├── manifest.json                # 包清单
├── package-index.json           # 文件索引
├── install.sh                   # 安装脚本（Linux/macOS）
├── install.ps1                  # 安装脚本（Windows）
├── verify.sh                    # 验证脚本
├── quality-gate.sh              # 质量检查脚本
├── docs/                        # 文档目录
│   ├── quality-report.md        # 质量报告
│   ├── acceptance-report.md     # 验收报告
│   └── architecture.md          # 架构文档
├── k8s/                         # Kubernetes 配置
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── deployments.yaml
│   ├── services.yaml
│   └── ingress.yaml
├── docker-compose/              # Docker Compose 配置
│   ├── docker-compose.yml
│   └── .env.template
├── init/                        # 初始化脚本
│   ├── run-init.sh
│   ├── postgres/
│   ├── minio/
│   └── qdrant/
├── images/                      # 镜像资源
│   ├── images.txt               # 镜像清单
│   └── archives/                # 镜像归档（可选）
├── scripts/                     # 辅助脚本
│   ├── load-images.sh
│   ├── collect-logs.sh
│   └── diagnose.sh
└── security/                    # 安全相关
    └── SHA256SUMS               # 校验和文件
```

### B. 配置文件说明

#### manifest.json

包清单文件，包含部署包的元数据：

```json
{
  "packageId": "pkg-20260908-abc123",
  "projectKey": "local-ai",
  "productVersion": "2.0.0",
  "sourceEnv": "dev",
  "targetEnv": "prod",
  "deployModes": ["k8s"],
  "database": "postgres",
  "imageMode": "image-archive"
}
```

#### package-index.json

文件索引，用于验证文件完整性。

### C. 脚本参数说明

#### install.sh

```bash
./install.sh [OPTIONS]

Options:
  --mode <k8s|docker-compose>   部署模式
  --namespace <name>            Kubernetes 命名空间（仅 k8s 模式）
  --interactive                 交互模式
  --dry-run                     模拟运行，不实际部署
  --skip-init                   跳过初始化步骤
  --help                        显示帮助信息
```

#### verify.sh

```bash
./verify.sh [OPTIONS]

Options:
  --verbose                     详细输出
  --report <file>              输出报告到文件
  --help                       显示帮助信息
```

### D. 相关文档

- [架构设计文档](docs/architecture.md)
- [API 文档](docs/api-reference.md)
- [运维手册](docs/operations-guide.md)
- [安全指南](docs/security-guide.md)

### E. 更新日志

请参考 `CHANGELOG.md` 文件了解版本变更历史。

---

**文档版本**: 1.0
**最后更新**: """ + datetime.now().strftime("%Y-%m-%d") + """
**维护**: Local AI 团队"""


# ============================================================================
# 辅助函数
# ============================================================================

def _get_service_description(service: str) -> str:
    """获取服务描述"""
    descriptions = {
        "iam": "身份认证和访问管理",
        "api-gateway": "API 网关和路由",
        "gateway": "API 网关",
        "config": "配置中心",
        "discovery": "服务发现",
        "monitor": "监控服务",
        "log": "日志服务",
        "audit": "审计服务",
        "eam": "企业资产管理",
        "mes": "制造执行系统",
        "erp": "企业资源规划",
        "aps": "高级计划排程",
        "wms": "仓库管理系统",
        "knowledge": "知识库服务",
    }
    return descriptions.get(service, f"{service.upper()} 服务")


def _get_service_port(service: str) -> str:
    """获取服务端口"""
    ports = {
        "iam": "8081",
        "api-gateway": "8080",
        "gateway": "8080",
        "config": "8888",
        "discovery": "8761",
        "monitor": "9090",
        "log": "9200",
        "audit": "8082",
        "eam": "8091",
        "mes": "8092",
        "erp": "8093",
        "aps": "8094",
        "wms": "8095",
        "knowledge": "8096",
    }
    return ports.get(service, "8080")


def _get_service_dependencies(service: str) -> str:
    """获取服务依赖"""
    dependencies = {
        "iam": "数据库",
        "api-gateway": "IAM, 服务发现",
        "gateway": "IAM",
        "config": "数据库",
        "discovery": "-",
        "monitor": "-",
        "log": "Elasticsearch",
        "audit": "数据库",
        "eam": "IAM, 数据库",
        "mes": "IAM, 数据库",
        "erp": "IAM, 数据库",
        "aps": "IAM, 数据库",
        "wms": "IAM, 数据库, MinIO",
        "knowledge": "IAM, 数据库, Qdrant",
    }
    return dependencies.get(service, "IAM, 数据库")


def _format_bytes(size_bytes: int) -> str:
    """格式化字节大小"""
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.2f} {units[unit_index]}"


from datetime import datetime
