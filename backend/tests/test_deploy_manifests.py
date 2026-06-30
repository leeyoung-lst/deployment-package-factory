from __future__ import annotations

from pathlib import Path

import yaml


def test_ingress_is_tuned_for_large_downloads() -> None:
    root = Path(__file__).resolve().parents[2]
    ingress = yaml.safe_load((root / "deploy" / "k8s" / "ingress.yaml").read_text(encoding="utf-8"))

    annotations = ingress["metadata"]["annotations"]
    assert annotations["nginx.ingress.kubernetes.io/proxy-buffering"] == "off"
    assert annotations["nginx.ingress.kubernetes.io/proxy-request-buffering"] == "off"
    assert annotations["nginx.ingress.kubernetes.io/proxy-read-timeout"] == "3600"
    assert annotations["nginx.ingress.kubernetes.io/proxy-send-timeout"] == "3600"
