"""Tests for unified error handling."""
from __future__ import annotations

from deployment_package_factory.services.deployment_packages.errors import (
    ErrorCategory,
    PackageBuildError,
    environment_error,
    kubernetes_error,
    image_export_error,
    validation_error,
)


def test_package_build_error_has_category_and_suggestion():
    error = PackageBuildError(
        "Missing required environment variable",
        category=ErrorCategory.ENVIRONMENT,
        suggestion="Set DEPLOYMENT_PACKAGE_DATABASE_URL in environment",
    )
    assert error.message == "Missing required environment variable"
    assert error.category == ErrorCategory.ENVIRONMENT
    assert error.suggestion == "Set DEPLOYMENT_PACKAGE_DATABASE_URL in environment"
    assert error.details == {}


def test_package_build_error_uses_default_suggestion():
    error = PackageBuildError("Something went wrong", category=ErrorCategory.KUBERNETES)
    assert error.suggestion == "检查 kubeconfig 配置和集群连接状态"


def test_package_build_error_to_dict():
    error = PackageBuildError(
        "Invalid image reference",
        category=ErrorCategory.VALIDATION,
        suggestion="Use format registry/repo:tag",
        details={"image": "invalid:image:ref"},
    )
    result = error.to_dict()
    assert result["message"] == "Invalid image reference"
    assert result["category"] == "validation"
    assert result["suggestion"] == "Use format registry/repo:tag"
    assert result["details"]["image"] == "invalid:image:ref"


def test_environment_error_factory():
    error = environment_error("Docker daemon not available", tool="docker")
    assert error.category == ErrorCategory.ENVIRONMENT
    assert error.details["tool"] == "docker"


def test_kubernetes_error_factory():
    error = kubernetes_error("Namespace not found", namespace="test")
    assert error.category == ErrorCategory.KUBERNETES
    assert error.details["namespace"] == "test"


def test_image_export_error_factory():
    error = image_export_error("Skopeo copy failed", exit_code=1)
    assert error.category == ErrorCategory.IMAGE_EXPORT
    assert error.details["exit_code"] == 1


def test_validation_error_factory():
    error = validation_error("Invalid project key", field="projectKey")
    assert error.category == ErrorCategory.VALIDATION
    assert error.details["field"] == "projectKey"


def test_error_categories_are_unique():
    categories = set(ErrorCategory)
    assert len(categories) == 10
    assert ErrorCategory.ENVIRONMENT in categories
    assert ErrorCategory.KUBERNETES in categories
    assert ErrorCategory.IMAGE_EXPORT in categories
