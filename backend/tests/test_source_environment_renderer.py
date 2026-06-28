from __future__ import annotations

from pathlib import Path

import yaml

from scripts.render_source_environments import render_source_environment_manifests


def test_source_environment_renderer_declares_dev_test_namespace_structure() -> None:
    content = render_source_environment_manifests(Path("deploy/source-environments/source-environments.yaml"))
    docs = [item for item in yaml.safe_load_all(content) if item]
    namespaces = {item["metadata"]["name"]: item for item in docs}

    assert set(namespaces) == {
        "dev-middleware-public",
        "dev-base-public",
        "dev-biz-eam-4x60",
        "dev-biz-mes-4x60",
        "dev-biz-mes-4x3",
        "test-middleware-public",
        "test-base-public",
        "test-biz-eam-4x60",
        "test-biz-mes-4x60",
        "test-biz-mes-4x3",
    }
    assert namespaces["dev-middleware-public"]["metadata"]["labels"]["local-ai.io/layer"] == "middleware"
    assert namespaces["test-base-public"]["metadata"]["labels"]["local-ai.io/layer"] == "base-platform"
    assert namespaces["test-biz-eam-4x60"]["metadata"]["labels"]["local-ai.io/environment"] == "test"
    assert namespaces["test-biz-eam-4x60"]["metadata"]["labels"]["local-ai.io/layer"] == "business"
    assert namespaces["test-biz-eam-4x60"]["metadata"]["labels"]["local-ai.io/product"] == "eam"
    assert namespaces["test-biz-eam-4x60"]["metadata"]["labels"]["local-ai.io/profile"] == "4x60"
    assert namespaces["dev-biz-mes-4x3"]["metadata"]["labels"]["local-ai.io/product"] == "mes"
    assert namespaces["dev-biz-mes-4x3"]["metadata"]["labels"]["local-ai.io/profile"] == "4x3"
