"""测试镜像版本管理和验证功能"""
import pytest

from deployment_package_factory.services.deployment_packages.image_version_manager import (
    parse_version,
    extract_version_from_tag,
    compare_versions,
    check_version_status,
    format_size,
    VersionInfo,
)


def test_parse_version_simple():
    """测试解析简单版本号"""
    version = parse_version("1.2.3")

    assert version is not None
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3
    assert version.pre_release == ""
    assert version.build_metadata == ""
    assert str(version) == "1.2.3"


def test_parse_version_with_v_prefix():
    """测试解析带 v 前缀的版本号"""
    version = parse_version("v1.2.3")

    assert version is not None
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3


def test_parse_version_with_pre_release():
    """测试解析带预发布标识的版本号"""
    version = parse_version("1.2.3-alpha")

    assert version is not None
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3
    assert version.pre_release == "alpha"
    assert str(version) == "1.2.3-alpha"


def test_parse_version_with_pre_release_and_number():
    """测试解析带预发布版本号的版本"""
    version = parse_version("1.2.3-beta.1")

    assert version is not None
    assert version.pre_release == "beta.1"
    assert str(version) == "1.2.3-beta.1"


def test_parse_version_with_build_metadata():
    """测试解析带构建元数据的版本号"""
    version = parse_version("1.2.3+build.123")

    assert version is not None
    assert version.build_metadata == "build.123"
    assert str(version) == "1.2.3+build.123"


def test_parse_version_full():
    """测试解析完整的语义化版本号"""
    version = parse_version("1.2.3-rc.1+build.456")

    assert version is not None
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3
    assert version.pre_release == "rc.1"
    assert version.build_metadata == "build.456"
    assert str(version) == "1.2.3-rc.1+build.456"


def test_parse_version_invalid():
    """测试解析无效版本号"""
    assert parse_version("invalid") is None
    assert parse_version("1.2") is None
    assert parse_version("1.2.3.4") is None
    assert parse_version("abc.def.ghi") is None


def test_version_is_stable():
    """测试判断是否为稳定版本"""
    stable = parse_version("1.2.3")
    unstable = parse_version("1.2.3-alpha")

    assert stable.is_stable() is True
    assert unstable.is_stable() is False


def test_extract_version_from_tag_simple():
    """测试从简单 tag 提取版本号"""
    version = extract_version_from_tag("myapp:1.2.3")

    assert version is not None
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3


def test_extract_version_from_tag_with_v_prefix():
    """测试从带 v 前缀的 tag 提取版本号"""
    version = extract_version_from_tag("myapp:v1.2.3")

    assert version is not None
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3


def test_extract_version_from_tag_with_suffix():
    """测试从带后缀的 tag 提取版本号"""
    version = extract_version_from_tag("myapp:1.2.3-alpine")

    assert version is not None
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3


def test_extract_version_from_tag_with_date_prefix():
    """测试从带日期前缀的 tag 提取版本号"""
    version = extract_version_from_tag("myapp:20231201-1.2.3")

    assert version is not None
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3


def test_extract_version_from_tag_no_version():
    """测试从没有版本号的 tag 提取"""
    assert extract_version_from_tag("myapp:latest") is None
    assert extract_version_from_tag("myapp:stable") is None
    assert extract_version_from_tag("myapp:dev") is None


def test_compare_versions_equal():
    """测试比较相等的版本"""
    v1 = parse_version("1.2.3")
    v2 = parse_version("1.2.3")

    assert compare_versions(v1, v2) == 0


def test_compare_versions_major():
    """测试比较主版本号不同的版本"""
    v1 = parse_version("2.0.0")
    v2 = parse_version("1.9.9")

    assert compare_versions(v1, v2) == 1
    assert compare_versions(v2, v1) == -1


def test_compare_versions_minor():
    """测试比较次版本号不同的版本"""
    v1 = parse_version("1.3.0")
    v2 = parse_version("1.2.9")

    assert compare_versions(v1, v2) == 1
    assert compare_versions(v2, v1) == -1


def test_compare_versions_patch():
    """测试比较修订号不同的版本"""
    v1 = parse_version("1.2.4")
    v2 = parse_version("1.2.3")

    assert compare_versions(v1, v2) == 1
    assert compare_versions(v2, v1) == -1


def test_compare_versions_pre_release():
    """测试比较预发布版本"""
    v1 = parse_version("1.2.3")
    v2 = parse_version("1.2.3-alpha")

    # 正式版本大于预发布版本
    assert compare_versions(v1, v2) == 1
    assert compare_versions(v2, v1) == -1


def test_compare_versions_pre_release_order():
    """测试预发布版本的排序"""
    v1 = parse_version("1.2.3-beta")
    v2 = parse_version("1.2.3-alpha")

    assert compare_versions(v1, v2) == 1
    assert compare_versions(v2, v1) == -1


def test_check_version_status_latest():
    """测试检查最新版本状态"""
    result = check_version_status("1.2.3", ["1.0.0", "1.1.0", "1.2.3"])

    assert result.status == "latest"
    assert result.latest_version == "1.2.3"
    assert "最新" in result.recommendation


def test_check_version_status_outdated():
    """测试检查过时版本状态"""
    result = check_version_status("1.0.0", ["1.0.0", "1.1.0", "1.2.3"])

    assert result.status == "outdated"
    assert result.latest_version == "1.2.3"
    assert "升级" in result.recommendation


def test_check_version_status_deprecated():
    """测试检查废弃版本状态"""
    result = check_version_status("1.0.0", ["1.0.0", "2.0.0", "3.0.0"])

    assert result.status == "deprecated"
    assert result.latest_version == "3.0.0"
    assert "升级" in result.recommendation
    assert "兼容性" in result.recommendation


def test_check_version_status_invalid_current():
    """测试检查无效的当前版本"""
    result = check_version_status("invalid", ["1.0.0", "1.1.0"])

    assert result.status == "unknown"
    assert "无法解析" in result.recommendation


def test_check_version_status_no_available():
    """测试没有可用版本"""
    result = check_version_status("1.0.0", [])

    assert result.status == "unknown"
    assert "无可用版本" in result.recommendation


def test_check_version_status_pre_release():
    """测试预发布版本状态"""
    result = check_version_status("1.3.0-alpha", ["1.0.0", "1.1.0", "1.2.0"])

    assert result.latest_version == "1.2.0"
    # 预发布版本可能比最新稳定版更新
    assert "预发布" in result.recommendation or "更新" in result.recommendation


def test_format_size_bytes():
    """测试格式化字节"""
    assert format_size(100) == "100.00 B"


def test_format_size_kilobytes():
    """测试格式化千字节"""
    assert format_size(1024) == "1.00 KB"
    assert format_size(2048) == "2.00 KB"


def test_format_size_megabytes():
    """测试格式化兆字节"""
    assert format_size(1024 * 1024) == "1.00 MB"
    assert format_size(5 * 1024 * 1024) == "5.00 MB"


def test_format_size_gigabytes():
    """测试格式化吉字节"""
    assert format_size(1024 * 1024 * 1024) == "1.00 GB"
    assert format_size(3 * 1024 * 1024 * 1024) == "3.00 GB"


def test_format_size_large():
    """测试格式化大文件"""
    assert "GB" in format_size(500 * 1024 * 1024 * 1024)


def test_version_info_string_representation():
    """测试 VersionInfo 的字符串表示"""
    v1 = VersionInfo(1, 2, 3, "", "", "1.2.3")
    assert str(v1) == "1.2.3"

    v2 = VersionInfo(1, 2, 3, "alpha", "", "1.2.3-alpha")
    assert str(v2) == "1.2.3-alpha"

    v3 = VersionInfo(1, 2, 3, "", "build.123", "1.2.3+build.123")
    assert str(v3) == "1.2.3+build.123"

    v4 = VersionInfo(1, 2, 3, "rc.1", "build.456", "1.2.3-rc.1+build.456")
    assert str(v4) == "1.2.3-rc.1+build.456"


def test_parse_various_version_formats():
    """测试解析各种版本格式"""
    test_cases = [
        ("1.0.0", (1, 0, 0)),
        ("v2.1.0", (2, 1, 0)),
        ("3.2.1-alpha", (3, 2, 1)),
        ("1.0.0-beta.2", (1, 0, 0)),
        ("2.0.0-rc.1+build.123", (2, 0, 0)),
    ]

    for version_str, (major, minor, patch) in test_cases:
        version = parse_version(version_str)
        assert version is not None
        assert version.major == major
        assert version.minor == minor
        assert version.patch == patch


def test_extract_version_from_various_tags():
    """测试从各种 tag 格式提取版本"""
    test_cases = [
        "nginx:1.21.0",
        "postgres:14.2",
        "redis:6.2.6-alpine",
        "myapp:v2.0.0",
        "service:20231201-1.5.0",
        "app:1.0.0-rc.1",
    ]

    for tag in test_cases:
        version = extract_version_from_tag(tag)
        assert version is not None, f"Failed to extract version from {tag}"
        assert version.major >= 0
        assert version.minor >= 0
        assert version.patch >= 0
