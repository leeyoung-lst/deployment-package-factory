"""智能错误提示系统 - 将技术错误转换为用户友好的消息"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ErrorCategory = Literal[
    "network",           # 网络连接问题
    "auth",              # 认证/授权问题
    "resource",          # 资源不足（磁盘、内存等）
    "configuration",     # 配置错误
    "dependency",        # 依赖缺失
    "permission",        # 权限问题
    "data",              # 数据问题（格式、完整性等）
    "timeout",           # 超时问题
    "external_service",  # 外部服务问题
    "internal",          # 内部错误
]


@dataclass
class ErrorDiagnosis:
    """错误诊断结果"""

    category: ErrorCategory
    """错误分类"""

    user_message: str
    """用户友好的错误描述"""

    technical_details: str
    """技术细节（可选展开查看）"""

    possible_causes: list[str]
    """可能的原因列表"""

    solutions: list[str]
    """解决方案步骤"""

    contact_support: bool = False
    """是否需要联系技术支持"""

    retry_recommended: bool = False
    """是否建议重试"""

    documentation_url: str = ""
    """相关文档链接"""


def diagnose_error(error: Exception, context: dict | None = None) -> ErrorDiagnosis:
    """
    诊断错误并返回用户友好的错误信息

    Args:
        error: 捕获的异常对象
        context: 错误上下文信息（如操作类型、环境等）

    Returns:
        ErrorDiagnosis 包含用户友好的错误信息和解决建议
    """
    context = context or {}
    error_message = str(error)
    error_type = type(error).__name__

    # 超时错误（在网络错误之前检查，因为超时也可能包含网络关键词）
    if _is_timeout_error(error, error_message):
        return _diagnose_timeout_error(error, error_message, context)

    # 网络连接错误
    if _is_network_error(error, error_message):
        return _diagnose_network_error(error, error_message, context)

    # 认证/授权错误
    if _is_auth_error(error, error_message):
        return _diagnose_auth_error(error, error_message, context)

    # 资源不足错误
    if _is_resource_error(error, error_message):
        return _diagnose_resource_error(error, error_message, context)

    # 配置错误
    if _is_config_error(error, error_message):
        return _diagnose_config_error(error, error_message, context)

    # 依赖缺失错误
    if _is_dependency_error(error, error_message):
        return _diagnose_dependency_error(error, error_message, context)

    # 权限错误
    if _is_permission_error(error, error_message):
        return _diagnose_permission_error(error, error_message, context)

    # 数据错误
    if _is_data_error(error, error_message):
        return _diagnose_data_error(error, error_message, context)

    # 外部服务错误
    if _is_external_service_error(error, error_message, context):
        return _diagnose_external_service_error(error, error_message, context)

    # 未知错误
    return _diagnose_unknown_error(error, error_message, context)


# ============================================================================
# 错误识别函数
# ============================================================================

def _is_network_error(error: Exception, message: str) -> bool:
    """判断是否为网络连接错误"""
    network_keywords = [
        "connection refused",
        "connection timeout",
        "network is unreachable",
        "no route to host",
        "connection reset",
        "failed to establish connection",
        "timeout",
        "timed out",
        "getaddrinfo failed",
        "name resolution failed",
    ]
    return any(keyword in message.lower() for keyword in network_keywords)


def _is_auth_error(error: Exception, message: str) -> bool:
    """判断是否为认证/授权错误"""
    auth_keywords = [
        "unauthorized",
        "authentication failed",
        "invalid credentials",
        "invalid token",
        "access denied",
        "forbidden",
        "401",
        "403",
        "unauthenticated",
    ]
    return any(keyword in message.lower() for keyword in auth_keywords)


def _is_resource_error(error: Exception, message: str) -> bool:
    """判断是否为资源不足错误"""
    resource_keywords = [
        "no space left",
        "disk full",
        "out of memory",
        "memory error",
        "insufficient",
        "quota exceeded",
        "too many files",
    ]
    return any(keyword in message.lower() for keyword in resource_keywords)


def _is_config_error(error: Exception, message: str) -> bool:
    """判断是否为配置错误"""
    from deployment_package_factory.services.deployment_packages.errors import PackageBuildError
    from deployment_package_factory.services.deployment_packages.catalog import CatalogError

    config_keywords = [
        "configuration",
        "invalid config",
        "missing config",
        "not found in catalog",
        "unsupported",
        "unknown project",
        "invalid option",
    ]
    return (
        isinstance(error, (PackageBuildError, CatalogError))
        or any(keyword in message.lower() for keyword in config_keywords)
    )


def _is_dependency_error(error: Exception, message: str) -> bool:
    """判断是否为依赖缺失错误"""
    dependency_keywords = [
        "not found",
        "no such file",
        "command not found",
        "module not found",
        "import error",
        "missing dependency",
        "skopeo",
        "docker",
    ]
    return any(keyword in message.lower() for keyword in dependency_keywords)


def _is_timeout_error(error: Exception, message: str) -> bool:
    """判断是否为超时错误"""
    import asyncio
    timeout_keywords = ["timeout", "timed out", "deadline exceeded"]
    return (
        isinstance(error, (TimeoutError, asyncio.TimeoutError))
        or any(keyword in message.lower() for keyword in timeout_keywords)
    )


def _is_permission_error(error: Exception, message: str) -> bool:
    """判断是否为权限错误"""
    permission_keywords = [
        "permission denied",
        "access is denied",
        "operation not permitted",
        "insufficient privileges",
        "requires root",
        "requires admin",
    ]
    return (
        isinstance(error, PermissionError)
        or any(keyword in message.lower() for keyword in permission_keywords)
    )


def _is_data_error(error: Exception, message: str) -> bool:
    """判断是否为数据错误"""
    data_keywords = [
        "invalid format",
        "parse error",
        "json decode",
        "yaml parse",
        "validation error",
        "integrity",
        "corrupt",
    ]
    return any(keyword in message.lower() for keyword in data_keywords)


def _is_external_service_error(error: Exception, message: str, context: dict) -> bool:
    """判断是否为外部服务错误"""
    service_keywords = [
        "registry",
        "kubernetes",
        "k8s",
        "api server",
        "cluster",
        "harbor",
        "docker hub",
    ]
    return any(keyword in message.lower() for keyword in service_keywords)


# ============================================================================
# 错误诊断函数
# ============================================================================

def _diagnose_network_error(error: Exception, message: str, context: dict) -> ErrorDiagnosis:
    """诊断网络连接错误"""
    return ErrorDiagnosis(
        category="network",
        user_message="无法连接到目标服务，请检查网络连接",
        technical_details=f"{type(error).__name__}: {message}",
        possible_causes=[
            "目标服务未启动或不可达",
            "网络防火墙阻止了连接",
            "服务地址或端口配置错误",
            "DNS 解析失败",
            "VPN 或代理配置问题",
        ],
        solutions=[
            "检查目标服务（如 Kubernetes 集群、镜像仓库）是否正常运行",
            "确认网络连接正常，可以访问目标地址",
            "检查防火墙规则，确保允许访问目标端口",
            "验证服务地址和端口配置是否正确",
            "如果使用 VPN，确认 VPN 连接正常",
        ],
        retry_recommended=True,
        documentation_url="/docs/troubleshooting/network",
    )


def _diagnose_auth_error(error: Exception, message: str, context: dict) -> ErrorDiagnosis:
    """诊断认证/授权错误"""
    return ErrorDiagnosis(
        category="auth",
        user_message="认证失败，无法访问目标资源",
        technical_details=f"{type(error).__name__}: {message}",
        possible_causes=[
            "访问令牌（Token）已过期或无效",
            "用户名或密码错误",
            "没有足够的权限访问资源",
            "Kubernetes ServiceAccount 权限不足",
            "镜像仓库凭据配置错误",
        ],
        solutions=[
            "检查 API_TOKEN 环境变量是否正确配置",
            "确认 Kubernetes 集群访问凭据有效",
            "验证镜像仓库的用户名和密码",
            "检查 ServiceAccount 是否有足够的 RBAC 权限",
            "尝试重新登录或刷新访问令牌",
        ],
        retry_recommended=False,
        documentation_url="/docs/troubleshooting/authentication",
    )


def _diagnose_resource_error(error: Exception, message: str, context: dict) -> ErrorDiagnosis:
    """诊断资源不足错误"""
    return ErrorDiagnosis(
        category="resource",
        user_message="系统资源不足，无法完成操作",
        technical_details=f"{type(error).__name__}: {message}",
        possible_causes=[
            "磁盘空间不足",
            "内存不足",
            "临时文件过多",
            "工作目录配额已满",
        ],
        solutions=[
            "清理旧的部署包和临时文件（使用清理功能）",
            "检查磁盘空间：df -h",
            "检查工作目录大小：du -sh /path/to/work",
            "考虑配置更大的工作目录或清理策略",
            "增加系统资源（磁盘、内存）",
        ],
        retry_recommended=True,
        documentation_url="/docs/troubleshooting/resources",
    )


def _diagnose_config_error(error: Exception, message: str, context: dict) -> ErrorDiagnosis:
    """诊断配置错误"""
    return ErrorDiagnosis(
        category="configuration",
        user_message="配置参数错误或不支持",
        technical_details=f"{type(error).__name__}: {message}",
        possible_causes=[
            "选择了不存在的项目或服务",
            "数据库类型不支持",
            "部署模式配置错误",
            "服务依赖关系不满足",
            "环境配置缺失",
        ],
        solutions=[
            "检查项目名称是否正确",
            "确认所选服务在目标环境中可用",
            "验证数据库类型是否支持（postgres、dm）",
            "检查服务依赖关系是否满足",
            "参考文档了解支持的配置选项",
        ],
        retry_recommended=False,
        documentation_url="/docs/configuration",
    )


def _diagnose_dependency_error(error: Exception, message: str, context: dict) -> ErrorDiagnosis:
    """诊断依赖缺失错误"""
    tool_missing = "skopeo" if "skopeo" in message.lower() else "docker" if "docker" in message.lower() else "未知工具"

    return ErrorDiagnosis(
        category="dependency",
        user_message=f"缺少必需的工具：{tool_missing}",
        technical_details=f"{type(error).__name__}: {message}",
        possible_causes=[
            f"{tool_missing} 未安装",
            f"{tool_missing} 不在 PATH 环境变量中",
            "工作容器镜像缺少必要工具",
        ],
        solutions=[
            f"安装 {tool_missing}（参考官方文档）",
            f"将 {tool_missing} 添加到 PATH 环境变量",
            "如果在容器中运行，确保工作镜像包含所需工具",
            "如果导出镜像失败，可以尝试使用 image-manifest 模式（不导出镜像归档）",
        ],
        retry_recommended=False,
        contact_support=True,
        documentation_url="/docs/installation/dependencies",
    )


def _diagnose_timeout_error(error: Exception, message: str, context: dict) -> ErrorDiagnosis:
    """诊断超时错误"""
    return ErrorDiagnosis(
        category="timeout",
        user_message="操作超时，可能是网络缓慢或服务响应慢",
        technical_details=f"{type(error).__name__}: {message}",
        possible_causes=[
            "网络速度过慢",
            "镜像仓库响应慢",
            "Kubernetes 集群负载高",
            "镜像过大导致拉取超时",
            "并发请求过多",
        ],
        solutions=[
            "检查网络连接速度",
            "稍后重试，避开高峰时段",
            "考虑增加超时时间配置",
            "检查目标服务（仓库、集群）是否正常",
            "减少并发构建任务数量",
        ],
        retry_recommended=True,
        documentation_url="/docs/troubleshooting/timeout",
    )


def _diagnose_permission_error(error: Exception, message: str, context: dict) -> ErrorDiagnosis:
    """诊断权限错误"""
    return ErrorDiagnosis(
        category="permission",
        user_message="权限不足，无法访问文件或资源",
        technical_details=f"{type(error).__name__}: {message}",
        possible_causes=[
            "工作目录权限不足",
            "文件系统只读",
            "用户权限不够",
            "SELinux 或 AppArmor 限制",
        ],
        solutions=[
            "检查工作目录权限：ls -la /path/to/work",
            "确保运行用户有读写权限",
            "如果在容器中运行，检查卷挂载权限",
            "检查 SELinux 配置：getenforce",
            "必要时使用管理员权限运行",
        ],
        retry_recommended=False,
        contact_support=True,
        documentation_url="/docs/troubleshooting/permissions",
    )


def _diagnose_data_error(error: Exception, message: str, context: dict) -> ErrorDiagnosis:
    """诊断数据错误"""
    return ErrorDiagnosis(
        category="data",
        user_message="数据格式错误或数据损坏",
        technical_details=f"{type(error).__name__}: {message}",
        possible_causes=[
            "配置文件格式错误（YAML、JSON）",
            "数据完整性校验失败",
            "文件损坏",
            "编码问题",
        ],
        solutions=[
            "检查配置文件格式是否正确",
            "使用 JSON/YAML 验证工具检查语法",
            "尝试重新生成配置",
            "检查文件是否完整，没有截断",
            "确认文件编码为 UTF-8",
        ],
        retry_recommended=False,
        documentation_url="/docs/troubleshooting/data-format",
    )


def _diagnose_external_service_error(error: Exception, message: str, context: dict) -> ErrorDiagnosis:
    """诊断外部服务错误"""
    service_name = "镜像仓库" if "registry" in message.lower() else "Kubernetes 集群" if "k8s" in message.lower() or "kubernetes" in message.lower() else "外部服务"

    return ErrorDiagnosis(
        category="external_service",
        user_message=f"{service_name}不可用或返回错误",
        technical_details=f"{type(error).__name__}: {message}",
        possible_causes=[
            f"{service_name}服务宕机或维护中",
            f"{service_name}网络不通",
            f"{service_name}负载过高",
            "API 版本不兼容",
            "服务配置变更",
        ],
        solutions=[
            f"检查{service_name}是否正常运行",
            f"确认{service_name}的访问地址和端口正确",
            "稍后重试，可能是临时故障",
            "检查服务日志了解详细错误",
            "联系服务管理员确认服务状态",
        ],
        retry_recommended=True,
        contact_support=True,
        documentation_url="/docs/troubleshooting/external-services",
    )


def _diagnose_unknown_error(error: Exception, message: str, context: dict) -> ErrorDiagnosis:
    """诊断未知错误"""
    return ErrorDiagnosis(
        category="internal",
        user_message="发生未预期的错误",
        technical_details=f"{type(error).__name__}: {message}",
        possible_causes=[
            "系统内部错误",
            "未处理的异常情况",
            "代码 bug",
        ],
        solutions=[
            "记录完整的错误信息",
            "尝试重新执行操作",
            "如果问题持续出现，联系技术支持",
            "提供操作步骤和错误日志以便排查",
        ],
        retry_recommended=True,
        contact_support=True,
        documentation_url="/docs/troubleshooting/general",
    )
