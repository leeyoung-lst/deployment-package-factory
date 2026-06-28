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

    assert result.namespace == "test-biz-eam-4x60"
    create_call = next(call for call in calls if call[0] == "POST")
    metadata = create_call[2]["metadata"]  # type: ignore[index]
    assert metadata["labels"][kubernetes_runtime.BUSINESS_KEY_LABEL] == "eam"
    assert kubernetes_runtime.BUSINESS_NAME_ANNOTATION not in metadata["labels"]
    assert metadata["annotations"][kubernetes_runtime.BUSINESS_NAME_ANNOTATION] == "设备管理"
    assert metadata["annotations"][kubernetes_runtime.BUSINESS_PROFILE_ANNOTATION] == "4x60"


def test_source_env_namespaces_includes_local_ai_labeled_namespaces(monkeypatch, tmp_path) -> None:
    token_path = tmp_path / "token"
    token_path.write_text("token", encoding="utf-8")
    monkeypatch.setenv("KUBERNETES_SERVICEACCOUNT_TOKEN_PATH", str(token_path))
    monkeypatch.delenv("DEPLOYMENT_PACKAGE_SOURCE_NAMESPACES_TEST", raising=False)
    monkeypatch.delenv("DEPLOYMENT_PACKAGE_SOURCE_NAMESPACES", raising=False)

    def fake_request_json(method: str, path: str, token: str, body: dict | None = None, content_type: str = "application/json") -> dict:
        if "local-ai.io/environment%3Dtest" in path or "local-ai.io/environment=test" in path:
            return {
                "items": [
                    {"metadata": {"name": "test-middleware-public"}},
                    {"metadata": {"name": "test-base-public"}},
                ]
            }
        if "deployment-package-factory.local-ai/environment%3Dtest" in path or "deployment-package-factory.local-ai/environment=test" in path:
            return {"items": [{"metadata": {"name": "test-biz-eam-4x60"}}]}
        return {"items": []}

    monkeypatch.setattr(kubernetes_runtime, "_request_json", fake_request_json)
    monkeypatch.setattr(kubernetes_runtime, "list_registered_business_platforms", lambda source_env: [])

    assert kubernetes_runtime.source_env_namespaces("test") == [
        "local-ai",
        "test-middleware-public",
        "test-base-public",
        "test-biz-eam-4x60",
    ]
