"""Unified error handling for deployment package factory.

This module provides structured error types with categories and user-friendly suggestions.
"""
from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
    """Error category for classification and user guidance."""

    # 环境配置错误
    ENVIRONMENT = "environment"
    # Kubernetes 运行时错误
    KUBERNETES = "kubernetes"
    # 镜像导出错误
    IMAGE_EXPORT = "image-export"
    # 依赖解析错误
    DEPENDENCY = "dependency"
    # 配置验证错误
    VALIDATION = "validation"
    # 文件系统错误
    FILESYSTEM = "filesystem"
    # 网络错误
    NETWORK = "network"
    # 权限错误
    PERMISSION = "permission"
    # 超时错误
    TIMEOUT = "timeout"
    # 内部错误
    INTERNAL = "internal"


class PackageBuildError(Exception):
    """Structured error for deployment package build failures.

    Args:
        message: Human-readable error message
        category: Error category for classification
        suggestion: User-friendly suggestion for resolution
        details: Optional additional context (not shown to end users)
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        suggestion: str | None = None,
        details: dict | None = None,
    ):
        self.message = message
        self.category = category
        self.suggestion = suggestion or self._default_suggestion(category)
        self.details = details or {}
        super().__init__(message)

    @staticmethod
    def _default_suggestion(category: ErrorCategory) -> str:
        """Get default suggestion based on error category."""
        suggestions = {
            ErrorCategory.ENVIRONMENT: "检查环境变量配置和依赖工具是否已安装",
            ErrorCategory.KUBERNETES: "检查 kubeconfig 配置和集群连接状态",
            ErrorCategory.IMAGE_EXPORT: "确保 skopeo 或 Docker 已安装且可用",
            ErrorCategory.DEPENDENCY: "检查服务依赖配置是否正确",
            ErrorCategory.VALIDATION: "检查请求参数和配置文件格式",
            ErrorCategory.FILESYSTEM: "检查文件系统权限和磁盘空间",
            ErrorCategory.NETWORK: "检查网络连接和镜像仓库可达性",
            ErrorCategory.PERMISSION: "检查当前用户权限和资源访问策略",
            ErrorCategory.TIMEOUT: "增加超时时间或检查资源是否响应",
            ErrorCategory.INTERNAL: "联系系统管理员或查看详细日志",
        }
        return suggestions.get(category, "请查看详细日志并联系技术支持")

    def to_dict(self) -> dict:
        """Convert error to dict for API response."""
        return {
            "message": self.message,
            "category": self.category.value,
            "suggestion": self.suggestion,
            "details": self.details,
        }


# Convenience factory functions for common error scenarios

def environment_error(message: str, suggestion: str | None = None, **details) -> PackageBuildError:
    """Create an environment configuration error."""
    return PackageBuildError(message, ErrorCategory.ENVIRONMENT, suggestion, details)


def kubernetes_error(message: str, suggestion: str | None = None, **details) -> PackageBuildError:
    """Create a Kubernetes runtime error."""
    return PackageBuildError(message, ErrorCategory.KUBERNETES, suggestion, details)


def image_export_error(message: str, suggestion: str | None = None, **details) -> PackageBuildError:
    """Create an image export error."""
    return PackageBuildError(message, ErrorCategory.IMAGE_EXPORT, suggestion, details)


def dependency_error(message: str, suggestion: str | None = None, **details) -> PackageBuildError:
    """Create a dependency resolution error."""
    return PackageBuildError(message, ErrorCategory.DEPENDENCY, suggestion, details)


def validation_error(message: str, suggestion: str | None = None, **details) -> PackageBuildError:
    """Create a validation error."""
    return PackageBuildError(message, ErrorCategory.VALIDATION, suggestion, details)


def filesystem_error(message: str, suggestion: str | None = None, **details) -> PackageBuildError:
    """Create a filesystem error."""
    return PackageBuildError(message, ErrorCategory.FILESYSTEM, suggestion, details)


def network_error(message: str, suggestion: str | None = None, **details) -> PackageBuildError:
    """Create a network error."""
    return PackageBuildError(message, ErrorCategory.NETWORK, suggestion, details)


def permission_error(message: str, suggestion: str | None = None, **details) -> PackageBuildError:
    """Create a permission error."""
    return PackageBuildError(message, ErrorCategory.PERMISSION, suggestion, details)


def timeout_error(message: str, suggestion: str | None = None, **details) -> PackageBuildError:
    """Create a timeout error."""
    return PackageBuildError(message, ErrorCategory.TIMEOUT, suggestion, details)


def internal_error(message: str, suggestion: str | None = None, **details) -> PackageBuildError:
    """Create an internal error."""
    return PackageBuildError(message, ErrorCategory.INTERNAL, suggestion, details)
