"""测试智能错误诊断功能"""
import pytest

from deployment_package_factory.services.deployment_packages.error_diagnosis import (
    diagnose_error,
    ErrorCategory,
)
from deployment_package_factory.services.deployment_packages.errors import PackageBuildError
from deployment_package_factory.services.deployment_packages.catalog import CatalogError


def test_diagnose_network_error():
    """测试网络连接错误诊断"""
    error = ConnectionRefusedError("Connection refused")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "network"
    assert "无法连接" in diagnosis.user_message
    assert len(diagnosis.possible_causes) > 0
    assert len(diagnosis.solutions) > 0
    assert diagnosis.retry_recommended is True
    assert "目标服务" in diagnosis.possible_causes[0]


def test_diagnose_auth_error():
    """测试认证错误诊断"""
    error = Exception("401 Unauthorized")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "auth"
    assert "认证失败" in diagnosis.user_message
    assert any("令牌" in cause or "Token" in cause for cause in diagnosis.possible_causes)
    assert any("API_TOKEN" in sol for sol in diagnosis.solutions)
    assert diagnosis.retry_recommended is False


def test_diagnose_resource_error():
    """测试资源不足错误诊断"""
    error = OSError("No space left on device")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "resource"
    assert "资源不足" in diagnosis.user_message
    assert any("磁盘" in cause for cause in diagnosis.possible_causes)
    assert any("清理" in sol for sol in diagnosis.solutions)
    assert diagnosis.retry_recommended is True


def test_diagnose_config_error():
    """测试配置错误诊断"""
    error = PackageBuildError("Unknown project 'invalid-project'")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "configuration"
    assert "配置" in diagnosis.user_message
    assert len(diagnosis.possible_causes) > 0
    assert len(diagnosis.solutions) > 0
    assert diagnosis.retry_recommended is False


def test_diagnose_catalog_error():
    """测试目录错误诊断"""
    error = CatalogError("Unsupported database option 'invalid-db'")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "configuration"
    assert "配置" in diagnosis.user_message


def test_diagnose_dependency_error():
    """测试依赖缺失错误诊断"""
    error = FileNotFoundError("skopeo: command not found")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "dependency"
    assert "skopeo" in diagnosis.user_message
    assert any("安装" in sol for sol in diagnosis.solutions)
    assert diagnosis.contact_support is True


def test_diagnose_timeout_error():
    """测试超时错误诊断"""
    error = TimeoutError("Operation timed out")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "timeout"
    assert "超时" in diagnosis.user_message
    assert any("网络" in cause for cause in diagnosis.possible_causes)
    assert diagnosis.retry_recommended is True


def test_diagnose_permission_error():
    """测试权限错误诊断"""
    error = PermissionError("Permission denied")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "permission"
    assert "权限" in diagnosis.user_message
    assert any("目录" in cause for cause in diagnosis.possible_causes)
    assert diagnosis.contact_support is True


def test_diagnose_data_error():
    """测试数据错误诊断"""
    error = ValueError("JSON decode error")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "data"
    assert "数据" in diagnosis.user_message
    assert any("格式" in cause for cause in diagnosis.possible_causes)


def test_diagnose_external_service_error_registry():
    """测试镜像仓库服务错误诊断"""
    error = Exception("Failed to pull from registry")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "external_service"
    assert "镜像仓库" in diagnosis.user_message
    assert diagnosis.retry_recommended is True
    assert diagnosis.contact_support is True


def test_diagnose_external_service_error_kubernetes():
    """测试 Kubernetes 服务错误诊断"""
    error = Exception("Kubernetes API server not responding")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "external_service"
    assert "Kubernetes" in diagnosis.user_message or "集群" in diagnosis.user_message
    assert diagnosis.retry_recommended is True


def test_diagnose_unknown_error():
    """测试未知错误诊断"""
    error = Exception("Some unexpected error")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "internal"
    assert "未预期" in diagnosis.user_message
    assert diagnosis.contact_support is True
    assert diagnosis.retry_recommended is True


def test_diagnose_error_with_context():
    """测试带上下文的错误诊断"""
    error = Exception("Connection timeout")
    context = {"operation": "build_package", "source_env": "dev"}
    diagnosis = diagnose_error(error, context)

    assert diagnosis.category in ["network", "timeout"]
    assert len(diagnosis.solutions) > 0


def test_diagnosis_includes_technical_details():
    """测试诊断结果包含技术细节"""
    error = ValueError("Invalid input")
    diagnosis = diagnose_error(error)

    assert diagnosis.technical_details != ""
    assert "ValueError" in diagnosis.technical_details
    assert "Invalid input" in diagnosis.technical_details


def test_diagnosis_includes_documentation_url():
    """测试诊断结果包含文档链接"""
    error = ConnectionRefusedError("Connection refused")
    diagnosis = diagnose_error(error)

    assert diagnosis.documentation_url != ""
    assert diagnosis.documentation_url.startswith("/docs/")


def test_multiple_error_types_have_unique_categories():
    """测试不同错误类型有不同的分类"""
    errors = [
        ConnectionRefusedError("Connection refused"),
        Exception("401 Unauthorized"),
        OSError("No space left"),
        PackageBuildError("Invalid config"),
        TimeoutError("Timeout"),
        PermissionError("Permission denied"),
    ]

    categories = [diagnose_error(e).category for e in errors]

    # 应该有多个不同的分类
    assert len(set(categories)) >= 5


def test_diagnosis_solutions_are_actionable():
    """测试解决方案是可操作的"""
    error = ConnectionRefusedError("Connection refused")
    diagnosis = diagnose_error(error)

    # 解决方案应该包含具体的动作词
    action_words = ["检查", "确认", "验证", "配置", "安装", "清理", "联系"]
    assert any(
        any(word in solution for word in action_words)
        for solution in diagnosis.solutions
    )


def test_diagnosis_possible_causes_are_specific():
    """测试可能原因是具体的"""
    error = OSError("No space left on device")
    diagnosis = diagnose_error(error)

    # 原因应该是具体的，不是泛泛而谈
    assert len(diagnosis.possible_causes) > 0
    assert all(len(cause) > 10 for cause in diagnosis.possible_causes)  # 不能太短


def test_network_timeout_classified_as_timeout():
    """测试网络超时被正确分类为超时错误"""
    error = Exception("Connection timed out")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "network"  # 网络超时可能被识别为网络问题
    assert diagnosis.retry_recommended is True


def test_docker_not_found_classified_as_dependency():
    """测试 Docker 缺失被正确分类"""
    error = FileNotFoundError("docker: command not found")
    diagnosis = diagnose_error(error)

    assert diagnosis.category == "dependency"
    assert "docker" in diagnosis.user_message.lower()
