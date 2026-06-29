from __future__ import annotations

from deployment_package_factory.settings import load_settings
from deployment_package_factory.services.settings import SystemSettings
from deployment_package_factory.services.settings_importer import import_environment_settings_from_xlsx


def test_load_settings_uses_deployment_package_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_DATABASE_URL", "postgresql://factory:secret@postgres:5432/factory")
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_OUTPUT_DIR", str(tmp_path / "packages"))
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_API_TOKEN", "secret-token")
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_MAX_CONCURRENT_BUILDS", "3")
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_EXECUTION_MODE", "worker")
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_WORKER_POLL_INTERVAL_SECONDS", "5")
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_WORKER_HEARTBEAT_SECONDS", "11")
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_RUNNING_TASK_TIMEOUT_MINUTES", "30")
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_RETENTION_DAYS", "7")
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_MAX_TOTAL_GB", "20")

    settings = load_settings()

    assert settings.data_dir == tmp_path / "data"
    assert settings.database_url == "postgresql://factory:secret@postgres:5432/factory"
    assert settings.output_dir == tmp_path / "packages"
    assert settings.api_token == "secret-token"
    assert settings.max_concurrent_builds == 3
    assert settings.execution_mode == "worker"
    assert settings.worker_poll_interval_seconds == 5
    assert settings.worker_heartbeat_seconds == 11
    assert settings.running_task_timeout_minutes == 30
    assert settings.retention_days == 7
    assert settings.max_total_gb == 20


def test_load_settings_clamps_invalid_concurrency(monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_MAX_CONCURRENT_BUILDS", "0")

    assert load_settings().max_concurrent_builds == 1


def test_load_settings_defaults_invalid_execution_mode(monkeypatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_PACKAGE_EXECUTION_MODE", "invalid")

    assert load_settings().execution_mode == "background"

    monkeypatch.setenv("DEPLOYMENT_PACKAGE_MAX_CONCURRENT_BUILDS", "not-a-number")

    assert load_settings().max_concurrent_builds == 1


def test_system_settings_defaults_include_environment_sections() -> None:
    settings = SystemSettings()

    assert settings.harbor.registry == "registry.local"
    assert settings.kubernetes.factory_namespace == "deployment-package-factory"
    assert settings.middleware.redis.enabled is True
    assert settings.middleware.redis.port == 6379
    assert settings.middleware.postgresql.database == "app"


def test_import_environment_settings_from_xlsx_reads_environment_workbook() -> None:
    path = _minimal_environment_workbook()
    result = import_environment_settings_from_xlsx(path, SystemSettings())

    assert result.settings.kubernetes.ingress_vip == "192.168.10.220"
    assert result.settings.kubernetes.factory_namespace == "deployment-package-factory"
    assert result.settings.harbor.registry == "192.168.10.210"
    assert result.settings.harbor.username == "admin"
    assert result.settings.jenkins.base_url == "http://192.168.10.211:8080"
    assert result.settings.jenkins.deploy_job == "deployment-package-factory-deploy-test"
    assert "harbor.registry" in result.imported_fields


def _minimal_environment_workbook():
    import tempfile
    import zipfile
    from pathlib import Path

    path = Path(tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False).name)
    sheets = [
        ("总览", [["项目", "内容"], ["K8S VIP / Ingress", "192.168.10.220"], ["镜像仓库", "Harbor 192.168.10.210"]]),
        ("VM与基础设施", [["名称", "IP/地址", "用途", "系统/组件", "账号", "密码/Token"], ["Harbor", "http://192.168.10.210", "", "", "admin", "secret"], ["Jenkins", "http://192.168.10.211:8080", "", "", "admin", "secret"]]),
        ("导包工厂环境", [["类别", "配置项", "建议/当前值"], ["K8s", "Namespace", "deployment-package-factory"]]),
        ("Jenkins与发布", [["类型", "名称/ID", "用途", "是否必需", "配置说明"], ["Job", "deployment-package-factory-deploy-test", "", "", ""]]),
        ("环境分区规划", [["环境", "Namespace 组", "服务类型"], ["测试", "base-public-test", "平台基础能力"]]),
    ]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "")
        archive.writestr("xl/workbook.xml", _workbook_xml([name for name, _ in sheets]))
        for index, (_, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))
    return path


def _workbook_xml(names: list[str]) -> str:
    sheet_xml = "".join(f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>' for index, name in enumerate(names, start=1))
    return f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{sheet_xml}</sheets></workbook>'


def _sheet_xml(rows: list[list[str]]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(f'<c r="{chr(65 + col)}{row_index}" t="inlineStr"><is><t>{value}</t></is></c>' for col, value in enumerate(row))
        row_xml.append(f'<row r="{row_index}">{cells}</row>')
    return f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(row_xml)}</sheetData></worksheet>'
