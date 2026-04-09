"""
PPT 解析服务
============
使用 python-pptx 读取 .pptx 文件，逐页提取文本、备注、表格内容。
图片与公式阶段一暂以占位符处理，阶段五集成 OCR 后补充。

保存位置：python-service/app/services/ppt_parser.py
"""

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches  # noqa: F401  # 保留引入，后续可能用于尺寸判断

from app.schemas.parse import PageContent, ParseResult
from app.utils.logger import logger


def parse_pptx(file_path: str, courseware_id: str) -> ParseResult:
    """
    解析 .pptx 文件，返回结构化的 ParseResult。

    Parameters
    ----------
    file_path : str
        .pptx 文件的绝对路径。
    courseware_id : str
        课件唯一标识（由 Java 后端传入）。

    Returns
    -------
    ParseResult
        包含每页文本、备注及图片占位符的解析结果。

    Raises
    ------
    FileNotFoundError
        文件路径不存在时抛出。
    ValueError
        文件非 .pptx 格式时抛出。
    """
    path = Path(file_path)

    # ---- 前置校验 ----
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")
    if path.suffix.lower() != ".pptx":
        raise ValueError(f"不支持的文件格式：{path.suffix}，期望 .pptx")

    logger.info("开始解析 PPT 文件：%s（courseware_id=%s）", file_path, courseware_id)

    prs = Presentation(str(path))
    pages: list[PageContent] = []

    for idx, slide in enumerate(prs.slides, start=1):
        # ---- 提取幻灯片文本 ----
        texts: list[str] = []
        image_placeholders: list[str] = []

        for shape in slide.shapes:
            # 文本框 / 自选图形中的文本
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    para_text = paragraph.text.strip()
                    if para_text:
                        texts.append(para_text)

            # 表格：逐行拼接单元格文本
            if shape.has_table:
                table = shape.table
                for row in table.rows:
                    row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_texts:
                        texts.append(" | ".join(row_texts))

            # 图片：阶段一仅记录占位标识
            if shape.shape_type == 13:  # MSO_SHAPE_TYPE.PICTURE = 13
                image_placeholders.append(f"[图片：slide_{idx}_img_{len(image_placeholders) + 1}]")

        # ---- 提取演讲者备注 ----
        notes_text = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()

        page = PageContent(
            page_index=idx,
            text="\n".join(texts),
            notes=notes_text,
            image_placeholders=image_placeholders,
        )
        pages.append(page)

    result = ParseResult(
        courseware_id=courseware_id,
        file_type="pptx",
        total_pages=len(pages),
        pages=pages,
    )

    logger.info(
        "PPT 解析完成：共 %d 页（courseware_id=%s）",
        result.total_pages,
        courseware_id,
    )
    return result
