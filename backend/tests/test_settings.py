from __future__ import annotations

from deployment_package_factory.settings import load_settings


def test_load_settings_uses_deployment_package_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_TASK_DB", str(tmp_path / "tasks.sqlite3"))
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_OUTPUT_DIR", str(tmp_path / "packages"))
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_MAX_CONCURRENT_BUILDS", "3")

    settings = load_settings()

    assert settings.data_dir == tmp_path / "data"
    assert settings.task_db_path == tmp_path / "tasks.sqlite3"
    assert settings.output_dir == tmp_path / "packages"
    assert settings.max_concurrent_builds == 3


def test_load_settings_clamps_invalid_concurrency(monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_MAX_CONCURRENT_BUILDS", "0")

    assert load_settings().max_concurrent_builds == 1

    monkeypatch.setenv("DEPLOYMENT_PACKAGE_MAX_CONCURRENT_BUILDS", "not-a-number")

    assert load_settings().max_concurrent_builds == 1
