from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from deployment_package_factory.services.settings import SystemSettings

NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


@dataclass(frozen=True)
class ImportedEnvironmentSettings:
    settings: SystemSettings
    imported_fields: list[str]
    warnings: list[str]


def import_environment_settings_from_xlsx(path: Path, current: SystemSettings | None = None) -> ImportedEnvironmentSettings:
    workbook = _read_workbook(path)
    settings = (current or SystemSettings()).model_copy(deep=True)
    imported: list[str] = []
    warnings: list[str] = []

    _apply_overview(workbook, settings, imported)
    _apply_infrastructure(workbook, settings, imported)
    _apply_factory_environment(workbook, settings, imported)
    _apply_jenkins(workbook, settings, imported)
    _apply_environment_plan(workbook, settings, imported)

    if not imported:
        warnings.append("未从 Excel 中识别到可导入的环境配置。")
    return ImportedEnvironmentSettings(settings=settings, imported_fields=sorted(set(imported)), warnings=warnings)


def _apply_overview(workbook: dict[str, list[list[str]]], settings: SystemSettings, imported: list[str]) -> None:
    rows = _rows(workbook, "总览")
    for row in rows:
        key, value = _cell(row, 0), _cell(row, 1)
        if key == "K8S VIP / Ingress" and value:
            settings.kubernetes.ingress_vip = value
            imported.append("kubernetes.ingressVip")
        elif key == "Namespace" and value:
            settings.kubernetes.default_namespace = value
            imported.append("kubernetes.defaultNamespace")
        elif key == "镜像仓库":
            host = _first_ip(value)
            if host:
                settings.harbor.registry = host
                imported.append("harbor.registry")


def _apply_infrastructure(workbook: dict[str, list[list[str]]], settings: SystemSettings, imported: list[str]) -> None:
    for row in _rows(workbook, "VM与基础设施") + _rows(workbook, "入口链接"):
        name, url, username, password = _cell(row, 0), _cell(row, 1), _cell(row, 4), _cell(row, 5)
        if name.lower() == "harbor":
            _set_harbor(settings, url, username, password, imported)
        elif name.lower() == "jenkins":
            _set_jenkins(settings, url, username, password, imported)


def _apply_factory_environment(workbook: dict[str, list[list[str]]], settings: SystemSettings, imported: list[str]) -> None:
    for row in _rows(workbook, "导包工厂环境"):
        category, item, value = _cell(row, 0), _cell(row, 1), _cell(row, 2)
        if category == "K8s" and item == "Namespace" and value:
            settings.kubernetes.factory_namespace = value
            imported.append("kubernetes.factoryNamespace")
        elif category == "代码仓库" and value:
            settings.git.group = settings.git.group or value
        elif category == "代码分支" and value:
            imported.append("git.defaultBranch")


def _apply_jenkins(workbook: dict[str, list[list[str]]], settings: SystemSettings, imported: list[str]) -> None:
    for row in _rows(workbook, "Jenkins与发布"):
        row_type, name, _, _, description = _cell(row, 0), _cell(row, 1), _cell(row, 2), _cell(row, 3), _cell(row, 4)
        if row_type == "Credential" and name == "dpf-registry-credentials":
            settings.jenkins.registry_credential_id = name
            imported.append("jenkins.registryCredentialId")
        elif row_type == "Credential" and name == "dpf-kubeconfig":
            settings.jenkins.kubeconfig_credential_id = name
            imported.append("jenkins.kubeconfigCredentialId")
        elif row_type == "Job" and "deploy" in name:
            settings.jenkins.deploy_job = name
            imported.append("jenkins.deployJob")
        elif row_type == "参数" and name == "REGISTRY":
            host = _first_ip(description)
            if host:
                settings.harbor.registry = host
                imported.append("harbor.registry")


def _apply_environment_plan(workbook: dict[str, list[list[str]]], settings: SystemSettings, imported: list[str]) -> None:
    for row in _rows(workbook, "环境分区规划"):
        env_name, namespace_group, service_type = _cell(row, 0), _cell(row, 1), _cell(row, 2)
        if env_name == "工具" and namespace_group:
            settings.kubernetes.factory_namespace = namespace_group
            imported.append("kubernetes.factoryNamespace")
        elif env_name == "测试" and namespace_group.startswith("base-public"):
            settings.kubernetes.default_namespace = namespace_group
            imported.append("kubernetes.defaultNamespace")
        if service_type and "平台基础能力" in service_type:
            settings.middleware.nacos.enabled = True


def _set_harbor(settings: SystemSettings, url: str, username: str, password: str, imported: list[str]) -> None:
    host = _url_host(url) or _first_ip(url)
    if host:
        settings.harbor.registry = host
        imported.append("harbor.registry")
    if username and username != "75":
        settings.harbor.username = username
        imported.append("harbor.username")
    if password and password != "75":
        settings.harbor.password = password
        imported.append("harbor.password")


def _set_jenkins(settings: SystemSettings, url: str, username: str, password: str, imported: list[str]) -> None:
    if url:
        settings.jenkins.base_url = url.split()[0]
        imported.append("jenkins.baseUrl")
    if username and username != "75":
        settings.jenkins.username = username
        imported.append("jenkins.username")
    if password and password != "75":
        settings.jenkins.password = password
        imported.append("jenkins.password")


def _read_workbook(path: Path) -> dict[str, list[list[str]]]:
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        sheet_names = _sheet_names(archive)
        return {
            name: _sheet_rows(archive, f"xl/worksheets/sheet{index}.xml", shared)
            for index, name in enumerate(sheet_names, start=1)
        }


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.itertext()) for node in root.findall("a:si", NS)]


def _sheet_names(archive: zipfile.ZipFile) -> list[str]:
    root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    return [node.attrib["name"] for node in root.findall("a:sheets/a:sheet", NS)]


def _sheet_rows(archive: zipfile.ZipFile, member: str, shared: list[str]) -> list[list[str]]:
    if member not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read(member))
    rows: list[list[str]] = []
    for row in root.findall(".//a:sheetData/a:row", NS):
        values: list[str] = []
        for cell in row.findall("a:c", NS):
            values.append(_cell_value(cell, shared))
        rows.append(values)
    return rows


def _cell_value(cell: ElementTree.Element, shared: list[str]) -> str:
    if cell.attrib.get("t") == "inlineStr":
        return "".join(cell.itertext()).strip()
    value = cell.findtext("a:v", default="", namespaces=NS)
    if cell.attrib.get("t") == "s" and value:
        return shared[int(value)]
    return value.strip()


def _rows(workbook: dict[str, list[list[str]]], sheet_name: str) -> list[list[str]]:
    return workbook.get(sheet_name, [])


def _cell(row: list[str], index: int) -> str:
    return row[index].strip() if index < len(row) else ""


def _first_ip(value: str) -> str:
    match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b", value)
    return match.group(0) if match else ""


def _url_host(value: str) -> str:
    match = re.search(r"https?://([^/\s]+)", value)
    return match.group(1) if match else ""
