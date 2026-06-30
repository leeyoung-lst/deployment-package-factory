from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


ENV_LABEL = "local-ai.io/environment"
LAYER_LABEL = "local-ai.io/layer"
PRODUCT_LABEL = "local-ai.io/product"
PROFILE_LABEL = "local-ai.io/profile"
SOURCE_ENV_LABEL = "local-ai.io/source-environment"
DPF_LABEL_PREFIX = "deployment-package-factory.local-ai"
DPF_ENV_LABEL = f"{DPF_LABEL_PREFIX}/environment"
DPF_NAMESPACE_TYPE_LABEL = f"{DPF_LABEL_PREFIX}/namespace-type"
DPF_BUSINESS_KEY_LABEL = f"{DPF_LABEL_PREFIX}/business-key"
DPF_STATUS_LABEL = f"{DPF_LABEL_PREFIX}/status"
MANAGED_BY_LABEL = "app.kubernetes.io/managed-by"
MANAGED_BY_VALUE = "deployment-package-factory"
REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Render source environment namespace manifests.")
    parser.add_argument("--config", default="deploy/source-environments/source-environments.yaml")
    parser.add_argument("--output-dir", default="deploy/source-environments")
    args = parser.parse_args()

    config_path = _repo_path(Path(args.config))
    output_dir = _repo_path(Path(args.output_dir))
    rendered = render_source_environment_manifests(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "namespaces.yaml").write_text(rendered, encoding="utf-8")
    (output_dir / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\n"
        "kind: Kustomization\n"
        "resources:\n"
        "  - namespaces.yaml\n",
        encoding="utf-8",
    )


def render_source_environment_manifests(config_path: Path) -> str:
    config_path = _repo_path(config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    documents: list[dict] = []
    for env in config.get("environments", []):
        env_name = _dns_label(env["name"])
        documents.append(_namespace(env["middlewareNamespace"], env_name, "middleware"))
        documents.append(_namespace(env["baseNamespace"], env_name, "base-platform"))
        for business in env.get("business", []):
            product = _dns_label(business["product"])
            profile = _dns_label(str(business["profile"]))
            namespace = business_namespace(env_name, product, profile)
            documents.append(
                _namespace(
                    namespace,
                    env_name,
                    "business",
                    product=product,
                    profile=profile,
                )
            )
    return "---\n".join(yaml.safe_dump(item, sort_keys=False, allow_unicode=True) for item in documents)


def _repo_path(path: Path) -> Path:
    if path.is_absolute() or path.exists():
        return path
    return REPO_ROOT / path


def business_namespace(env: str, product: str, profile: str) -> str:
    return f"{_dns_label(env)}-biz-{_dns_label(product)}-{_dns_label(profile)}"


def _namespace(
    name: str,
    env: str,
    layer: str,
    *,
    product: str = "",
    profile: str = "",
) -> dict:
    labels = {
        MANAGED_BY_LABEL: MANAGED_BY_VALUE,
        SOURCE_ENV_LABEL: "true",
        ENV_LABEL: env,
        LAYER_LABEL: layer,
        DPF_ENV_LABEL: env,
        DPF_NAMESPACE_TYPE_LABEL: layer,
        DPF_STATUS_LABEL: "active",
    }
    if product:
        labels[PRODUCT_LABEL] = product
        labels[DPF_BUSINESS_KEY_LABEL] = product
    if profile:
        labels[PROFILE_LABEL] = profile
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": _dns_label(name),
            "labels": labels,
        },
    }


def _dns_label(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", str(value).strip().lower()).strip("-")
    normalized = re.sub(r"-+", "-", normalized)
    if not normalized:
        raise ValueError("DNS label cannot be empty.")
    if len(normalized) > 63:
        raise ValueError(f"DNS label is too long: {value!r}")
    return normalized


if __name__ == "__main__":
    main()
