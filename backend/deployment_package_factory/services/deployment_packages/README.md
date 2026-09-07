# Deployment Package Services

部署包生成服务的核心模块，负责从运行时环境生成生产交付包。

## 模块架构

### 核心构建器
- **builder.py** - 部署包构建主流程编排器
  - 协调各个 renderer 生成配置文件
  - 管理镜像导出流程
  - 生成最终的 tar.gz 归档包

### 渲染器模块（Renderers）
每个 renderer 负责生成特定类型的配置文件：

- **deployment_renderer.py** - 生成 K8s/Docker Compose 部署配置
- **init_script_renderer.py** - 生成数据库和中间件初始化脚本
- **verify_renderer.py** - 生成包完整性校验脚本（shell + PowerShell）
- **mcp_verify_renderer.py** - 生成 MCP 服务端到端验证脚本
- **quality_renderer.py** - 生成质量门禁检查脚本
- **acceptance_report_renderer.py** - 生成验收报告模板
- **project_overlay_renderer.py** - 生成项目级专属配置

### 工具模块
- **image_manager.py** - 镜像导出管理（Docker/skopeo/containerd）
  - 预检查镜像可用性
  - 支持多种导出方式（registry/runtime/local）
  - 生成镜像归档和加载脚本

- **errors.py** - 统一错误处理
  - `PackageBuildError` - 包构建错误
  - `ImageExportError` - 镜像导出错误
  - `handle_build_error()` - 错误上下文包装

- **kubernetes_runtime.py** - K8s 运行时交互
  - 读取 ConfigMap/Secret
  - 创建镜像导出 Pod
  - 管理命名空间和资源

- **dependency_resolver.py** - 依赖解析
  - 基础平台 → 业务产品 → 中间件依赖树
  - 项目模板默认值应用

- **microservice_delivery.py** - 微服务交付状态管理
- **task_executor.py** - 后台任务执行器

## 典型流程

### 1. 预览部署包
```python
manifest = preview_deployment_package(request)
# 返回解析后的依赖、镜像清单、警告信息
```

### 2. 构建部署包
```python
result = build_deployment_package(
    manifest=manifest,
    image_mode="archive",  # 或 "manifest"
    output_dir=Path("data/packages")
)
# 生成完整的 tar.gz 归档包
```

### 3. 镜像导出（可选）
```python
from deployment_package_factory.services.deployment_packages.image_manager import (
    export_images_with_runner,
    check_image_export_environment
)

# 预检查
env = check_image_export_environment()
# {'runner': 'skopeo', 'available': True, ...}

# 导出
export_images_with_runner(
    image_entries=manifest.images,
    archive_dir=package_root / "images",
    runner=env["runner"]
)
```

## 错误处理

所有模块使用统一的错误类型：

```python
from deployment_package_factory.services.deployment_packages.errors import (
    handle_build_error,
    PackageBuildError,
    ImageExportError
)

# 在构建过程中
with handle_build_error("导出镜像", task_id=task.id):
    export_images_with_runner(...)
```

## 测试

```bash
# 运行所有测试
pytest tests/

# 测试特定模块
pytest tests/test_deployment_package_builder.py -v
pytest tests/test_image_manager.py -v
pytest tests/test_errors.py -v
```

## 配置

通过 `settings.py` 加载环境配置：
- `KUBECONFIG` - K8s 集群访问
- `DEPLOYMENT_PACKAGE_OUTPUT_DIR` - 产物目录
- `EXECUTION_MODE` - `local` 或 `worker`
- `IMAGE_EXPORT_CONCURRENCY` - 并发导出数
