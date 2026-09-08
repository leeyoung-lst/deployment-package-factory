"""配置文件预览功能的数据模型"""
from pydantic import BaseModel, ConfigDict, Field


def _camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class PreviewFile(BaseModel):
    """单个预览文件的内容"""
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)

    path: str  # 文件在部署包中的相对路径
    content: str  # 文件内容（文本）
    language: str = "text"  # 语法高亮语言：yaml, json, shell, text
    size: int = 0  # 文件大小（字节）
    truncated: bool = False  # 是否被截断（超过大小限制）


class PackagePreviewResponse(BaseModel):
    """部署包配置预览响应"""
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel)

    package_id: str
    files: list[PreviewFile] = Field(default_factory=list)
    available_files: list[str] = Field(default_factory=list)  # 可预览的文件列表
