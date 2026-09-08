# K8s 环境验证方案

**环境信息**（从 local-ai-k8s-environment-v2.xlsx 读取）

---

## 📋 环境概况

- **环境名称**: local-ai-assistant K8S 高可用环境
- **K8S VIP / Ingress**: 192.168.10.220
- **Namespace**: local-ai
- **K8S 版本**: v1.36.1
- **节点 OS**: Ubuntu 24.04.4 LTS
- **容器运行时**: containerd 2.2.1
- **镜像仓库**: Harbor 192.168.10.210

## 🏭 导包工厂配置

- **命名空间**: deployment-package-factory（与 local-ai 业务隔离）
- **部署模式**: backend + worker + frontend + 外部 PostgreSQL + RWX PVC
- **凭据管理**: Jenkins Credentials 管理
- **验收重点**: Jenkins 构建 → Harbor 推送 → K8s 部署 → 页面导包 → SHA256 校验

---

## ✅ 验证清单

### 1. 环境连通性验证

```bash
#!/bin/bash
# verify_k8s_connectivity.sh

echo "=== K8s 环境连通性验证 ==="

# 1. 检查 kubectl 配置
echo "1. 检查 kubectl 连接..."
kubectl cluster-info
kubectl version --short

# 2. 检查节点状态
echo -e "\n2. 检查节点状态..."
kubectl get nodes -o wide

# 3. 检查命名空间
echo -e "\n3. 检查命名空间..."
kubectl get namespace deployment-package-factory
kubectl get namespace local-ai

# 4. 检查 Ingress VIP
echo -e "\n4. 检查 Ingress 可达性..."
ping -c 3 192.168.10.220

# 5. 检查 Harbor 镜像仓库
echo -e "\n5. 检查 Harbor 连接..."
curl -k https://192.168.10.210/api/v2.0/health

echo -e "\n=== 环境连通性验证完成 ==="
```

### 2. 部署包工厂部署验证

```bash
#!/bin/bash
# verify_factory_deployment.sh

NAMESPACE="deployment-package-factory"

echo "=== 部署包工厂部署验证 ==="

# 1. 检查 Deployment
echo "1. 检查 Deployments..."
kubectl get deployments -n $NAMESPACE

# 2. 检查 Pods
echo -e "\n2. 检查 Pods 状态..."
kubectl get pods -n $NAMESPACE -o wide

# 3. 检查 Services
echo -e "\n3. 检查 Services..."
kubectl get svc -n $NAMESPACE

# 4. 检查 Ingress
echo -e "\n4. 检查 Ingress..."
kubectl get ingress -n $NAMESPACE

# 5. 检查 PVC（持久卷）
echo -e "\n5. 检查 PVC..."
kubectl get pvc -n $NAMESPACE

# 6. 检查 ConfigMap 和 Secret
echo -e "\n6. 检查配置..."
kubectl get configmap -n $NAMESPACE
kubectl get secret -n $NAMESPACE

# 7. 查看 Pod 日志（backend）
echo -e "\n7. 查看 backend 日志（最近 20 行）..."
BACKEND_POD=$(kubectl get pods -n $NAMESPACE -l app=deployment-package-factory-backend -o jsonpath='{.items[0].metadata.name}')
if [ -n "$BACKEND_POD" ]; then
    kubectl logs -n $NAMESPACE $BACKEND_POD --tail=20
else
    echo "未找到 backend Pod"
fi

echo -e "\n=== 部署验证完成 ==="
```

### 3. 功能验证

```bash
#!/bin/bash
# verify_factory_functions.sh

INGRESS_HOST="192.168.10.220"
FACTORY_PATH="/deployment-package-factory"  # 根据实际 Ingress 配置调整

echo "=== 功能验证 ==="

# 1. 健康检查
echo "1. 健康检查..."
curl -v "http://${INGRESS_HOST}${FACTORY_PATH}/api/health" 2>&1 | grep -E "HTTP|health"

# 2. 测试创建构建任务
echo -e "\n2. 创建测试构建任务..."
RESPONSE=$(curl -s -X POST "http://${INGRESS_HOST}${FACTORY_PATH}/api/deployment-packages/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "projectKey": "test-k8s-verify",
    "sourceEnv": "dev",
    "targetEnv": "prod",
    "deployModes": ["k8s"],
    "database": "postgres",
    "platformServices": ["iam"],
    "businessServices": []
  }')

echo "响应: $RESPONSE"

# 提取任务 ID
TASK_ID=$(echo $RESPONSE | grep -o '"taskId":"[^"]*"' | cut -d'"' -f4)

if [ -n "$TASK_ID" ]; then
    echo "任务 ID: $TASK_ID"
    
    # 3. 查询任务状态
    echo -e "\n3. 查询任务状态..."
    sleep 2
    curl -s "http://${INGRESS_HOST}${FACTORY_PATH}/api/deployment-packages/tasks/${TASK_ID}" | jq '.'
    
    # 4. 持续查询直到完成（最多 5 分钟）
    echo -e "\n4. 等待构建完成..."
    for i in {1..60}; do
        STATUS=$(curl -s "http://${INGRESS_HOST}${FACTORY_PATH}/api/deployment-packages/tasks/${TASK_ID}" | jq -r '.status')
        PROGRESS=$(curl -s "http://${INGRESS_HOST}${FACTORY_PATH}/api/deployment-packages/tasks/${TASK_ID}" | jq -r '.progress')
        echo "[$i/60] 状态: $STATUS, 进度: $PROGRESS%"
        
        if [ "$STATUS" = "completed" ]; then
            echo "✅ 构建完成！"
            break
        elif [ "$STATUS" = "failed" ]; then
            echo "❌ 构建失败"
            curl -s "http://${INGRESS_HOST}${FACTORY_PATH}/api/deployment-packages/tasks/${TASK_ID}" | jq '.error'
            break
        fi
        
        sleep 5
    done
else
    echo "❌ 创建任务失败"
fi

echo -e "\n=== 功能验证完成 ==="
```

### 4. 数据库连接验证

```bash
#!/bin/bash
# verify_database.sh

NAMESPACE="deployment-package-factory"

echo "=== 数据库连接验证 ==="

# 从 ConfigMap 或 Secret 获取数据库连接信息
DB_HOST=$(kubectl get configmap -n $NAMESPACE factory-config -o jsonpath='{.data.DB_HOST}' 2>/dev/null || echo "未配置")
DB_NAME=$(kubectl get configmap -n $NAMESPACE factory-config -o jsonpath='{.data.DB_NAME}' 2>/dev/null || echo "未配置")

echo "数据库主机: $DB_HOST"
echo "数据库名称: $DB_NAME"

# 如果可以访问 Pod，尝试从 Pod 内部测试连接
BACKEND_POD=$(kubectl get pods -n $NAMESPACE -l app=deployment-package-factory-backend -o jsonpath='{.items[0].metadata.name}')

if [ -n "$BACKEND_POD" ]; then
    echo -e "\n从 Pod 内部测试数据库连接..."
    kubectl exec -n $NAMESPACE $BACKEND_POD -- sh -c "python -c 'import psycopg2; print(\"数据库连接测试：OK\")' 2>&1" || echo "数据库连接失败"
else
    echo "未找到 backend Pod"
fi

echo -e "\n=== 数据库验证完成 ==="
```

### 5. 镜像仓库验证

```bash
#!/bin/bash
# verify_harbor.sh

HARBOR_HOST="192.168.10.210"
PROJECT="deployment-package-factory"

echo "=== Harbor 镜像仓库验证 ==="

# 1. 检查 Harbor 健康状态
echo "1. 检查 Harbor 健康状态..."
curl -sk https://${HARBOR_HOST}/api/v2.0/health | jq '.'

# 2. 检查项目是否存在
echo -e "\n2. 检查项目..."
# 需要 Harbor 凭据，这里只做基础连通性测试
curl -sk https://${HARBOR_HOST}/api/v2.0/projects | head -20

# 3. 从 K8s Secret 获取镜像拉取凭据
echo -e "\n3. 检查镜像拉取凭据..."
kubectl get secret -n deployment-package-factory -o yaml | grep dockerconfigjson | head -1

echo -e "\n=== Harbor 验证完成 ==="
```

---

## 🚀 快速验证脚本

将所有验证合并到一个脚本：

```bash
#!/bin/bash
# full_verification.sh

set -e

echo "=============================================="
echo "  K8s 环境完整验证"
echo "=============================================="

echo -e "\n[1/5] 环境连通性验证..."
bash verify_k8s_connectivity.sh

echo -e "\n[2/5] 部署包工厂部署验证..."
bash verify_factory_deployment.sh

echo -e "\n[3/5] 数据库连接验证..."
bash verify_database.sh

echo -e "\n[4/5] Harbor 镜像仓库验证..."
bash verify_harbor.sh

echo -e "\n[5/5] 功能验证..."
bash verify_factory_functions.sh

echo -e "\n=============================================="
echo "  验证完成！"
echo "=============================================="
```

---

## 📊 验证检查清单

### 环境层
- [ ] kubectl 可以连接到集群
- [ ] 所有节点状态为 Ready
- [ ] Ingress VIP (192.168.10.220) 可以访问
- [ ] Harbor (192.168.10.210) 可以访问

### 部署层
- [ ] deployment-package-factory 命名空间存在
- [ ] backend Pod 运行正常
- [ ] worker Pod 运行正常（如果有）
- [ ] frontend Pod 运行正常
- [ ] Service 正确暴露端口
- [ ] Ingress 配置正确
- [ ] PVC 绑定成功

### 功能层
- [ ] API 健康检查通过
- [ ] 可以创建构建任务
- [ ] 任务状态正确更新
- [ ] 构建任务可以完成
- [ ] 可以下载部署包
- [ ] SHA256 校验通过

### 集成层
- [ ] 数据库连接正常
- [ ] 可以访问 Harbor
- [ ] 可以从 Harbor 拉取镜像
- [ ] K8s API 访问正常（列出 Pods/Services）

---

## 🔧 常见问题排查

### 问题 1：Pod 无法启动

```bash
# 查看 Pod 详情
kubectl describe pod <pod-name> -n deployment-package-factory

# 查看事件
kubectl get events -n deployment-package-factory --sort-by='.lastTimestamp'

# 查看日志
kubectl logs <pod-name> -n deployment-package-factory
```

### 问题 2：Ingress 无法访问

```bash
# 检查 Ingress
kubectl describe ingress -n deployment-package-factory

# 检查 Ingress Controller
kubectl get pods -n ingress-nginx

# 测试 Service 端口转发
kubectl port-forward -n deployment-package-factory svc/deployment-package-factory-backend 8000:8000
curl http://localhost:8000/api/health
```

### 问题 3：镜像拉取失败

```bash
# 检查 ImagePullSecrets
kubectl get secret -n deployment-package-factory

# 测试镜像拉取
kubectl run test --image=192.168.10.210/deployment-package-factory/backend:latest \
  -n deployment-package-factory --dry-run=client -o yaml
```

### 问题 4：数据库连接失败

```bash
# 从 Pod 内部测试
kubectl exec -it <backend-pod> -n deployment-package-factory -- sh

# 在 Pod 内
ping <db-host>
psql -h <db-host> -U <db-user> -d <db-name>
```

---

## 📝 验证报告模板

```markdown
# K8s 环境验证报告

**验证日期**: YYYY-MM-DD
**验证人员**: 
**环境**: local-ai-assistant K8S (192.168.10.220)

## 验证结果

| 验证项 | 状态 | 备注 |
|-------|------|------|
| 环境连通性 | ✅/❌ | |
| Pod 状态 | ✅/❌ | |
| Service 状态 | ✅/❌ | |
| Ingress 访问 | ✅/❌ | |
| 数据库连接 | ✅/❌ | |
| Harbor 连接 | ✅/❌ | |
| API 健康检查 | ✅/❌ | |
| 创建构建任务 | ✅/❌ | |
| 任务完成 | ✅/❌ | |
| 下载部署包 | ✅/❌ | |

## 问题记录

1. 问题描述
   - 严重程度: 
   - 解决方案: 

## 建议

- 
```

---

**创建日期**: 2026-09-08  
**环境**: local-ai-assistant K8s v1.36.1  
**文档状态**: 待执行
