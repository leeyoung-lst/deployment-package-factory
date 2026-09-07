"""image_utils 模块单元测试"""

import pytest

from deployment_package_factory.services.deployment_packages.image_utils import (
    image_path_without_tag,
    has_registry,
    with_default_tag,
    target_image_ref,
    safe_image_filename,
    normalize_image_id,
    split_image_tag,
    image_registry_priority,
    source_registry_host,
    runtime_image_match_score,
    matches_catalog_image,
)
from deployment_package_factory.services.deployment_packages.errors import PackageBuildError


class TestImagePathWithoutTag:
    """测试 image_path_without_tag 函数"""

    def test_with_registry_and_tag(self):
        assert image_path_without_tag("registry.example.com/myapp/backend:v1.0") == "myapp/backend"

    def test_with_tag_only(self):
        assert image_path_without_tag("myapp/backend:latest") == "myapp/backend"

    def test_with_digest(self):
        assert image_path_without_tag("myapp/backend@sha256:abc123") == "myapp/backend"

    def test_with_registry_and_digest(self):
        assert image_path_without_tag("registry.example.com/myapp@sha256:abc") == "myapp"

    def test_no_tag_no_registry(self):
        assert image_path_without_tag("myapp/backend") == "myapp/backend"

    def test_single_name(self):
        assert image_path_without_tag("nginx") == "nginx"


class TestHasRegistry:
    """测试 has_registry 函数"""

    def test_with_domain_registry(self):
        assert has_registry("registry.example.com/myapp:v1") is True

    def test_with_localhost(self):
        assert has_registry("localhost:5000/myapp:v1") is True

    def test_with_port(self):
        assert has_registry("10.0.0.1:5000/myapp") is True

    def test_without_registry(self):
        assert has_registry("myapp:v1") is False

    def test_docker_hub_style(self):
        assert has_registry("library/nginx") is False

    def test_single_name(self):
        assert has_registry("nginx") is False


class TestWithDefaultTag:
    """测试 with_default_tag 函数"""

    def test_add_default_tag(self):
        assert with_default_tag("myapp", "prod") == "myapp:prod"

    def test_keep_existing_tag(self):
        assert with_default_tag("myapp:v1.0", "prod") == "myapp:v1.0"

    def test_keep_digest(self):
        assert with_default_tag("myapp@sha256:abc", "prod") == "myapp@sha256:abc"

    def test_with_registry(self):
        assert with_default_tag("registry.example.com/myapp", "prod") == "registry.example.com/myapp:prod"

    def test_empty_image_raises_error(self):
        with pytest.raises(PackageBuildError):
            with_default_tag("", "prod")

    def test_whitespace_only_raises_error(self):
        with pytest.raises(PackageBuildError):
            with_default_tag("   ", "prod")


class TestTargetImageRef:
    """测试 target_image_ref 函数"""

    def test_add_registry(self):
        assert target_image_ref("myapp:v1", "registry.example.com/project") == "registry.example.com/project/myapp:v1"

    def test_remove_local_ai_prefix(self):
        assert target_image_ref("local-ai/myapp:v1", "registry.example.com/project") == "registry.example.com/project/myapp:v1"

    def test_replace_registry(self):
        result = target_image_ref("old-registry.com/local-ai/myapp:v1", "registry.example.com/project")
        assert result == "registry.example.com/project/myapp:v1"

    def test_remove_project_prefix(self):
        result = target_image_ref("project/myapp:v1", "registry.example.com/project")
        assert result == "registry.example.com/project/myapp:v1"

    def test_no_registry_returns_source(self):
        assert target_image_ref("myapp:v1", "") == "myapp:v1"

    def test_nested_path(self):
        result = target_image_ref("local-ai/sub/myapp:v1", "registry.example.com/project")
        assert result == "registry.example.com/project/sub/myapp:v1"


class TestSafeImageFilename:
    """测试 safe_image_filename 函数"""

    def test_replace_special_chars(self):
        assert safe_image_filename("registry.example.com/myapp:v1.0") == "registry.example.com_myapp_v1.0"

    def test_keep_alphanumeric(self):
        assert safe_image_filename("myapp123") == "myapp123"

    def test_replace_slashes(self):
        assert safe_image_filename("path/to/image") == "path_to_image"

    def test_replace_at_sign(self):
        assert safe_image_filename("myapp@sha256:abc") == "myapp_sha256_abc"

    def test_multiple_special_chars(self):
        assert safe_image_filename("my-app:v1.0@sha256") == "my-app_v1.0_sha256"


class TestNormalizeImageId:
    """测试 normalize_image_id 函数"""

    def test_remove_docker_pullable_prefix(self):
        assert normalize_image_id("docker-pullable://myapp@sha256:abc") == "myapp@sha256:abc"

    def test_remove_containerd_prefix(self):
        assert normalize_image_id("containerd://myapp@sha256:abc") == "myapp@sha256:abc"

    def test_remove_docker_prefix(self):
        assert normalize_image_id("docker://myapp@sha256:abc") == "myapp@sha256:abc"

    def test_no_prefix(self):
        assert normalize_image_id("myapp@sha256:abc") == "myapp@sha256:abc"

    def test_unknown_prefix(self):
        assert normalize_image_id("unknown://myapp@sha256:abc") == "unknown://myapp@sha256:abc"


class TestSplitImageTag:
    """测试 split_image_tag 函数"""

    def test_split_simple_tag(self):
        assert split_image_tag("myapp:v1.0") == ("myapp", "v1.0")

    def test_split_with_registry(self):
        assert split_image_tag("registry.example.com/myapp:latest") == ("registry.example.com/myapp", "latest")

    def test_no_tag(self):
        assert split_image_tag("myapp") == ("myapp", "")

    def test_with_digest_no_tag(self):
        assert split_image_tag("myapp@sha256:abc") == ("myapp", "")

    def test_nested_path_with_tag(self):
        assert split_image_tag("path/to/myapp:v1") == ("path/to/myapp", "v1")

    def test_port_in_registry(self):
        assert split_image_tag("localhost:5000/myapp:latest") == ("localhost:5000/myapp", "latest")


class TestImageRegistryPriority:
    """测试 image_registry_priority 函数"""

    def test_with_registry(self):
        assert image_registry_priority("registry.example.com/myapp:v1") == 1

    def test_without_registry(self):
        assert image_registry_priority("myapp:v1") == 0

    def test_localhost(self):
        assert image_registry_priority("localhost:5000/myapp") == 1


class TestSourceRegistryHost:
    """测试 source_registry_host 函数"""

    def test_extract_host(self):
        assert source_registry_host("registry.example.com:5000/myapp:v1") == "registry.example.com:5000"

    def test_extract_simple_host(self):
        assert source_registry_host("registry.example.com/myapp:v1") == "registry.example.com"

    def test_no_registry(self):
        assert source_registry_host("myapp:v1") == ""

    def test_localhost(self):
        assert source_registry_host("localhost:5000/myapp") == "localhost:5000"


class TestEdgeCases:
    """边缘情况测试"""

    def test_empty_strings(self):
        """测试空字符串处理"""
        assert image_path_without_tag("") == ""
        assert has_registry("") is False
        assert source_registry_host("") == ""

    def test_unicode_characters(self):
        """测试 Unicode 字符处理"""
        result = safe_image_filename("myapp-中文:v1.0")
        assert "myapp" in result
        assert "v1.0" in result

    def test_very_long_image_name(self):
        """测试超长镜像名"""
        long_name = "a" * 1000
        result = image_path_without_tag(f"{long_name}:v1")
        assert result == long_name

    def test_multiple_colons(self):
        """测试多个冒号（registry 带端口 + 标签）"""
        image = "localhost:5000/myapp:v1.0"
        path, tag = split_image_tag(image)
        assert path == "localhost:5000/myapp"
        assert tag == "v1.0"

    def test_multiple_slashes(self):
        """测试多层路径"""
        image = "registry.example.com/org/team/project/myapp:v1"
        assert has_registry(image) is True
        path = image_path_without_tag(image)
        assert path == "org/team/project/myapp"


class TestRuntimeImageMatchScore:
    """测试 runtime_image_match_score 函数"""

    def test_exact_match(self):
        """完全匹配返回 100"""
        assert runtime_image_match_score("myapp/backend:v1", "myapp/backend:v1") == 100

    def test_path_match_different_tags(self):
        """路径匹配但标签不同返回 100"""
        assert runtime_image_match_score("myapp/backend:v1", "myapp/backend:v2") == 100

    def test_base_name_match(self):
        """基础名称匹配返回 80"""
        assert runtime_image_match_score("project/backend:v1", "myapp/backend:v1") == 80

    def test_local_ai_prefix_in_runtime(self):
        """运行时镜像有 local-ai- 前缀返回 70"""
        assert runtime_image_match_score("backend:v1", "local-ai-backend:v1") == 70

    def test_local_ai_prefix_in_catalog(self):
        """目录镜像有 local-ai- 前缀返回 60"""
        assert runtime_image_match_score("local-ai-backend:v1", "backend:v1") == 60

    def test_no_match(self):
        """不匹配返回 0"""
        assert runtime_image_match_score("frontend:v1", "backend:v1") == 0

    def test_with_registry(self):
        """带注册表的匹配"""
        score = runtime_image_match_score(
            "registry.example.com/myapp/backend:v1",
            "registry.example.com/myapp/backend:v2"
        )
        assert score == 100


class TestMatchesCatalogImage:
    """测试 matches_catalog_image 函数"""

    def test_matches_one_image(self):
        """匹配列表中的一个镜像"""
        catalog = ["frontend:v1", "backend:v1", "database:v1"]
        assert matches_catalog_image(catalog, "backend:v1") is True

    def test_matches_with_default_tag(self):
        """使用默认标签匹配"""
        catalog = ["backend"]
        assert matches_catalog_image(catalog, "backend:prod") is True

    def test_matches_local_ai_prefix(self):
        """匹配带 local-ai- 前缀的镜像"""
        catalog = ["backend"]
        assert matches_catalog_image(catalog, "local-ai-backend:prod") is True

    def test_no_match(self):
        """不匹配任何镜像"""
        catalog = ["frontend:v1", "database:v1"]
        assert matches_catalog_image(catalog, "backend:v1") is False

    def test_empty_catalog(self):
        """空目录返回 False"""
        assert matches_catalog_image([], "backend:v1") is False

    def test_custom_default_tag(self):
        """自定义默认标签"""
        catalog = ["backend"]
        assert matches_catalog_image(catalog, "backend:latest", default_tag="latest") is True

