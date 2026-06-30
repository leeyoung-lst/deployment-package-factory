from __future__ import annotations

from typing import Protocol


class RuntimeEnvProbeLike(Protocol):
    env: dict[str, str]


def probe_env_values(probes: list[RuntimeEnvProbeLike]) -> tuple[dict[str, str], dict[str, str]]:
    values: dict[str, str] = {}
    sources: dict[str, str] = {}
    for probe in probes:
        for name, value in probe.env.items():
            if value and (name not in values or not is_resolved_value(values[name])):
                values[name] = str(value)
                sources[name] = "pod-env"
    return values, sources


def merge_env_values(
    probe_values: dict[str, str],
    probe_sources: dict[str, str],
    runtime_env: dict[str, str],
    overrides: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    values = dict(probe_values)
    sources = dict(probe_sources)
    for name, raw_value in runtime_env.items():
        value = str(raw_value)
        if is_resolved_value(value) or name not in values:
            values[name] = value
            sources[name] = "source-secret" if is_resolved_value(value) else "catalog"
    for name, raw_value in overrides.items():
        values[name] = str(raw_value)
        sources[name] = "user"
    return values, sources


def is_resolved_value(value: str) -> bool:
    return bool(value) and "__REPLACE_WITH_" not in str(value)
