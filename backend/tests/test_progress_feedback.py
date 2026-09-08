"""测试实时进度反馈功能"""

from deployment_package_factory.services.deployment_packages.builder import build_deployment_package
from deployment_package_factory.services.deployment_packages.models import PackageBuildRequest


def test_progress_callback_is_invoked():
    """测试进度回调函数被正确调用"""
    progress_updates = []

    def capture_progress(progress: int, message: str):
        progress_updates.append({"progress": progress, "message": message})

    request = PackageBuildRequest(
        projectKey="",  # 不使用项目模板
        sourceEnv="dev",
        targetEnv="prod",
        platformServices=["iam"],
        businessServices=[],
        deployModes=["k8s"],
        database="postgres",  # 使用正确的数据库键名
        imageMode="image-manifest",
        targetProfile={"exportImages": False},
    )

    result = build_deployment_package(request, progress_callback=capture_progress)

    # 验证进度回调被调用
    assert len(progress_updates) > 0, "进度回调应该被调用"

    # 验证进度从小到大递增
    progresses = [update["progress"] for update in progress_updates]
    assert progresses[0] == 5, f"第一个进度应该是 5%，实际: {progresses[0]}"
    assert progresses[-1] == 100, f"最后一个进度应该是 100%，实际: {progresses[-1]}"
    assert all(progresses[i] <= progresses[i + 1] for i in range(len(progresses) - 1)), "进度应该递增"

    # 验证关键阶段都有进度更新
    messages = [update["message"] for update in progress_updates]
    assert any("初始化" in msg for msg in messages), f"应该有初始化阶段，实际消息: {messages}"
    assert any("依赖" in msg for msg in messages), f"应该有依赖解析阶段，实际消息: {messages}"
    assert any("配置" in msg for msg in messages), f"应该有配置生成阶段，实际消息: {messages}"
    assert any("完成" in msg for msg in messages), f"应该有完成提示，实际消息: {messages}"

    # 打印所有进度更新用于调试
    print("\n进度更新记录:")
    for update in progress_updates:
        print(f"  {update['progress']:3d}% - {update['message']}")

    # 验证构建成功
    assert result.package_id.startswith("pkg-")
    assert result.artifact_size > 0


def test_build_without_progress_callback():
    """测试不提供进度回调时构建仍正常工作"""
    request = PackageBuildRequest(
        projectKey="",  # 不使用项目模板
        sourceEnv="dev",
        targetEnv="prod",
        platformServices=["iam"],
        businessServices=[],
        deployModes=["k8s"],
        database="postgres",  # 使用正确的数据库键名
        imageMode="image-manifest",
        targetProfile={"exportImages": False},
    )

    # 不提供 progress_callback，应该正常构建
    result = build_deployment_package(request, progress_callback=None)

    assert result.package_id.startswith("pkg-")
    assert result.artifact_size > 0
