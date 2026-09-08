"""手动验证配置预览功能"""
import json
from pathlib import Path
import sys
import tempfile

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from deployment_package_factory.services.deployment_packages.preview_service import (
    preview_package_files,
    detect_language,
)


def test_preview():
    """手动测试配置预览"""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # 创建测试包
        package_root = tmp_path / "local-ai-prod-package-pkg-20260908-test"
        package_root.mkdir()

        # 创建测试文件
        manifest = {"packageId": "pkg-20260908-test", "projectKey": "test"}
        (package_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        readme = "# 部署包 README\n\n这是测试部署包。"
        (package_root / "README.md").write_text(readme, encoding="utf-8")

        # 预览
        result = preview_package_files(package_root, requested_files=["manifest.json", "README.md"])

        print("✓ 预览成功")
        print(f"  包ID: {result.package_id}")
        print(f"  文件数: {len(result.files)}")

        for file in result.files:
            print(f"\n  文件: {file.path}")
            print(f"    语言: {file.language}")
            print(f"    大小: {file.size} 字节")
            print(f"    截断: {file.truncated}")
            print(f"    内容预览: {file.content[:100]}...")

        # 验证中文正确
        readme_file = next(f for f in result.files if f.path == "README.md")
        assert "部署包 README" in readme_file.content, "中文内容应正确显示"
        print("\n✓ 中文编码测试通过")

        # 验证语言检测
        assert detect_language("test.yaml") == "yaml"
        assert detect_language("test.json") == "json"
        assert detect_language("test.sh") == "shell"
        print("✓ 语言检测测试通过")

        print("\n✅ 所有测试通过")


if __name__ == "__main__":
    test_preview()
