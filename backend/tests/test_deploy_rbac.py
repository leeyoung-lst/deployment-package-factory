from __future__ import annotations

from pathlib import Path

import yaml


def test_runtime_reader_rbac_can_read_runtime_config_sources() -> None:
    root = Path(__file__).resolve().parents[2]
    docs = list(yaml.safe_load_all((root / "deploy" / "k8s" / "rbac.yaml").read_text(encoding="utf-8")))
    role = next(item for item in docs if item.get("kind") == "ClusterRole")

    read_resources = {
        resource
        for rule in role.get("rules", [])
        if {"get", "list"}.issubset(set(rule.get("verbs", [])))
        for resource in rule.get("resources", [])
    }

    assert {"pods", "secrets", "configmaps"}.issubset(read_resources)
