from __future__ import annotations

from deployment_package_factory.services.deployment_packages import kubernetes_runtime


def test_register_business_platform_stores_display_fields_in_annotations(monkeypatch, tmp_path) -> None:
    token_path = tmp_path / "token"
    token_path.write_text("token", encoding="utf-8")
    monkeypatch.setenv("KUBERNETES_SERVICEACCOUNT_TOKEN_PATH", str(token_path))
    calls: list[tuple[str, str, dict | None, str]] = []

    def fake_request_json(method: str, path: str, token: str, body: dict | None = None, content_type: str = "application/json") -> dict:
        calls.append((method, path, body, content_type))
        if method == "GET":
            return {}
        return {}

    monkeypatch.setattr(kubernetes_runtime, "_request_json", fake_request_json)

    result = kubernetes_runtime.register_business_platform("test", "eam", "设备管理", "4x60")

    assert result.namespace == "test-business-eam"
    create_call = next(call for call in calls if call[0] == "POST")
    metadata = create_call[2]["metadata"]  # type: ignore[index]
    assert metadata["labels"][kubernetes_runtime.BUSINESS_KEY_LABEL] == "eam"
    assert kubernetes_runtime.BUSINESS_NAME_ANNOTATION not in metadata["labels"]
    assert metadata["annotations"][kubernetes_runtime.BUSINESS_NAME_ANNOTATION] == "设备管理"
    assert metadata["annotations"][kubernetes_runtime.BUSINESS_PROFILE_ANNOTATION] == "4x60"
