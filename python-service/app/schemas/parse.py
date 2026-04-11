"""
数据模型（Schemas）
==================
遵照规约 1.2：统一响应格式 code / message / data。
遵照规约 3.2：请求/响应模型使用 Pydantic。

保存位置：python-service/app/schemas/parse.py
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ============================================================
# 通用响应模型（所有接口复用）
# ============================================================

class BaseResponse(BaseModel):
    """
    统一响应体，与 Java 后端格式保持一致。

    Attributes
    ----------
    code : int
        状态码。0 表示成功，非 0 表示错误（40001 客户端错误，50001 服务端错误）。
    message : str
        描述信息。成功时为 "success"，失败时为错误描述。
    data : Any | None
        返回数据。成功时为具体数据对象或列表，失败时为 null。
    """
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


# ============================================================
# 解析相关模型
# ============================================================

class PageContent(BaseModel):
    """
    单页解析结果。

    Attributes
    ----------
    page_index : int
        页码（从 1 开始）。
    text : str
        该页提取的纯文本内容。
    notes : str
        备注 / 演讲者注释（仅 PPT 有，PDF 为空字符串）。
    image_placeholders : list[str]
        图片占位标识列表。阶段二先返回占位标识，
        阶段五集成 OCR 后填充图片内文字。
    formula_placeholders : list[str]
        公式占位标识列表。阶段二先返回占位标识，
        阶段五集成公式识别（如 LaTeX OCR）后填充公式内容。
    """
    page_index: int = Field(..., ge=1, description="页码，从 1 开始")
    text: str = Field(default="", description="该页提取的纯文本内容")
    notes: str = Field(default="", description="备注/演讲者注释")
    image_placeholders: list[str] = Field(
        default_factory=list,
        description="图片占位标识列表",
    )
    formula_placeholders: list[str] = Field(
        default_factory=list,
        description="公式占位标识列表，阶段二为占位，阶段五填充实际内容",
    )


class ParseResult(BaseModel):
    """
    完整解析结果，包含所有页面。

    Attributes
    ----------
    courseware_id : str
        课件唯一标识（由 Java 后端生成并传入）。
    file_type : str
        文件类型："pptx" 或 "pdf"。
    total_pages : int
        总页数。
    pages : list[PageContent]
        各页解析内容列表。
    """
    courseware_id: str = Field(..., description="课件唯一标识")
    file_type: str = Field(..., description="文件类型：pptx / pdf")
    total_pages: int = Field(..., ge=0, description="总页数")
    pages: list[PageContent] = Field(default_factory=list, description="各页解析内容")


class ParseRequest(BaseModel):
    """
    解析请求体（由 Java 后端调用时传入）。

    Attributes
    ----------
    courseware_id : str
        课件唯一标识。
    file_path : str
        文件在服务器上的绝对路径或 MinIO URL。
    """
    courseware_id: str = Field(..., description="课件唯一标识")
    file_path: str = Field(..., description="文件路径或 MinIO URL")
