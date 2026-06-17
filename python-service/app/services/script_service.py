from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

try:  # pragma: no cover - real LangChain prompt templates are used when installed
    from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
except ImportError:  # pragma: no cover - lightweight equivalent for slim runtime/test environments
    @dataclass
    class _FallbackPromptMessage:
        content: str
        type: str

    @dataclass
    class _FallbackMessageTemplate:
        template: str
        message_type: str

        @classmethod
        def from_template(cls, template: str):
            return cls(template=template, message_type="human")

        def format(self, **kwargs: Any) -> _FallbackPromptMessage:
            return _FallbackPromptMessage(content=self.template.format(**kwargs), type=self.message_type)

    class SystemMessagePromptTemplate(_FallbackMessageTemplate):
        @classmethod
        def from_template(cls, template: str):
            return cls(template=template, message_type="system")

    class HumanMessagePromptTemplate(_FallbackMessageTemplate):
        @classmethod
        def from_template(cls, template: str):
            return cls(template=template, message_type="human")

    class ChatPromptTemplate:
        def __init__(self, templates: list[_FallbackMessageTemplate]) -> None:
            self._templates = templates

        @classmethod
        def from_messages(cls, templates: list[_FallbackMessageTemplate]):
            return cls(templates)

        def format_messages(self, **kwargs: Any) -> list[_FallbackPromptMessage]:
            return [template.format(**kwargs) for template in self._templates]

from app.clients.llm_client import get_llm_client
from app.core.config import settings
from app.core.exceptions import AppException, ModelOutputException, PythonServiceException, THIRD_PARTY_SERVICE_ERROR
from app.schemas.script import PageScript, ScriptGenerateRequest, ScriptGenerateResponse
from app.utils.logger import logger

SCRIPT_TEMPERATURE = 0.0
SCRIPT_PAGE_CHUNK_SIZE = 7
SCRIPT_PAGE_MAX_TOKENS = 1800
SCRIPT_CHUNK_RETRY_ATTEMPTS = 2

_SYSTEM_TEMPLATE = """\
你是一位经验丰富的中文课程讲师，要把课件页面整理成适合口播的视频讲稿。

你的目标不是“读 PPT”，而是“用中文把页面里的知识点讲明白”。

必须遵守：
1. 全程用中文讲解。页面里如果出现英文术语，可以保留少量术语原文，但解释必须是中文。
2. 不要按页码报幕，不要说“现在我们来看第几页”“下一页继续看”“这一页主要讲的是”。
3. 不要照抄作者名、学校名、文件名、页眉页脚、装饰文字、提交提示、无关英文碎片。
4. 如果页面本身是英文，也要优先输出中文解释，不要整段改成英文口播。
5. 总纲页、目录页、章节页、练习提示页、总结页要短；概念页、公式页、例题页要像老师一样把知识点讲开。
6. 不能编造页面之外的事实、数据和结论，只能基于给定页面信息做更自然的中文解释。
7. 只输出合法 JSON，不要输出 Markdown，不要输出代码块，不要解释规则。
8. 所有字符串值里都不要出现半角双引号 "。如果需要强调术语，请直接写术语本身，或者使用中文引号“”。
9. 所有字符串值必须写成单行文本，不要在 JSON 字符串里换行。
"""

_JSON_SCHEMA_EXAMPLE = """\
{
  "courseware_id": "<与请求一致>",
  "opening": "<简短中文开场白>",
  "pages": [
    {
      "page_index": 1,
      "script": "<本页中文讲稿>",
      "transition": ""
    }
  ],
  "closing": "<简短中文结束语>"
}"""

_FEW_SHOT_EXAMPLES = """\
示例 1
输入页面：
- title: CNN Layer
- page_role: overview
- teacher_goal: 先搭框架，只讲本节要点和结构，不展开细节。
- clean_text: Fully Connected Layer / Convolution Layer / Pooling Layer

期望输出页面：
{
  "page_index": 1,
  "script": "这一部分先把卷积神经网络里几类核心层的分工理清楚。后面会分别展开全连接层、卷积层和池化层，重点理解它们各自负责什么，以及组合起来后怎样完成特征提取与分类。",
  "transition": ""
}

示例 2
输入页面：
- title: Convolution Layer: Example
- page_role: formula_detail
- teacher_goal: 把公式或计算关系讲清楚，重点说明变量和结果的关系。
- clean_text: Input volume 32x32x3, 10 filters 5x5, stride 1, pad 2, output volume size

期望输出页面：
{
  "page_index": 12,
  "script": "这里是在练习卷积层输出尺寸的计算。关键不是把数字逐个念出来，而是先分清输入大小、卷积核大小、步长和填充分别影响什么，再据此判断空间尺寸和通道数怎样变化。",
  "transition": ""
}

示例 3
输入页面：
- title: Upload your answer to
- page_role: overview
- teacher_goal: 这是练习提示页，只做简短说明。
- clean_text: upload your answer to

期望输出页面：
{
  "page_index": 20,
  "script": "这一页是练习或提交提示，本身不承载新的知识点，知道需要按要求完成对应练习即可。",
  "transition": ""
}

示例 4
输入页面：
- title: Fully Connected Layer
- page_role: concept_detail
- teacher_goal: 把概念讲明白，强调定义、作用、结构和关系。
- clean_text: 32x32x3 image stretch to 3072x1, dot product, weights

期望输出页面：
{
  "page_index": 4,
  "script": "这里重点理解全连接层怎样把前面提取到的特征送入分类器。核心做法是先把多维特征拉平成一维向量，再让每个输出神经元和全部输入相连，从而综合所有特征做最后判断。",
  "transition": ""
}

示例 5
输入页面：
- title: Max Pooling
- page_role: concept_detail
- teacher_goal: 把概念讲明白，说明池化到底保留了什么、舍弃了什么。
- clean_text: max pooling, 2x2 region, keep the strongest response, downsample

期望输出页面：
{
  "page_index": 18,
  "script": "这里重点理解最大池化为什么能压缩特征图，同时还保留最显著的信息。它会在每个局部窗口里只留下响应最大的那个值，所以空间尺寸变小了，但最突出的局部特征通常还能被保留下来。",
  "transition": ""
}

示例 6
输入页面：
- title: Convolution Layer: Summary
- page_role: summary
- teacher_goal: 用简短中文把前面卷积层的关键结论收住。
- clean_text: local connectivity, parameter sharing, stride, padding, output size

期望输出页面：
{
  "page_index": 26,
  "script": "这里可以把卷积层的关键点收成几条主线：局部连接决定它擅长抓局部模式，参数共享决定它比全连接更省参数，而步长、填充和卷积核大小一起决定输出尺寸和感受范围。",
  "transition": ""
}

示例 7
输入页面：
- title: A closer look at spatial dimensions
- page_role: formula_detail
- teacher_goal: 用中文解释尺寸为什么会变化，不要把英文 bullet 原样念出来。
- clean_text: 7x7 input, 3x3 filter, stride 2, 3x3 output

期望输出页面：
{
  "page_index": 14,
  "script": "这一页关注的是卷积后空间尺寸为什么会缩小。输入大小固定时，卷积核每次移动得更快，也就是步长更大，那么能落下来的有效位置就会变少，所以输出特征图的宽和高都会相应减小。",
  "transition": ""
}
"""

_ANTI_PATTERN_EXAMPLES = """\
错误示例 1
{
  "page_index": 1,
  "script": "现在我们来看第1页，这一页主要在讲 Convolution Layer，下一页继续看输出尺寸。",
  "transition": "接下来我们继续下一页"
}
错误原因：报页码、口头过渡太多、直接读英文标题、transition 非空。
正确方向：直接用中文解释卷积层的作用，transition 固定为空字符串。

错误示例 2
{
  "page_index": 2,
  "script": "Input volume is 32x32x3, output volume size is 32x32x10.",
  "transition": ""
}
错误原因：整段英文，没有做中文讲解。
正确方向：用中文解释输入尺寸、卷积核数量和输出尺寸之间的关系，只保留必要术语。

错误示例 3
{
  "page_index": 3,
  "script": "Fully Connected Layer, dot product, weights, 3072x1.",
  "transition": ""
}
错误原因：只是抄标题和 bullet，没有真正讲知识点。
正确方向：解释全连接层怎样把多维特征拉平、综合并送入分类器。
"""

_HUMAN_TEMPLATE = """\
请根据下面的课件信息生成逐页讲稿。

课件 ID：{courseware_id}
学科：{subject}
总页数：{total_pages}

核心要求：
1. pages 数量尽量与输入页数一致，page_index 必须与输入页码对应。
2. 每页 script 必须像老师在讲知识点，不要报页码，不要念 PPT，不要念作者、学校、文件名。
3. 页面出现英文时，要优先输出中文解释；必要时可在中文里保留少量英文术语。
4. overview / divider / summary / low_value 页面控制在 1 到 2 句。
5. concept_detail / formula_detail / example_detail / generic 页面控制在 2 到 4 句，要解释知识点本身，不要空泛复述。
6. transition 一律输出空字符串 ""，不要写任何过渡话。
7. opening 和 closing 要简短、自然，不要读文件名。
8. 所有字符串值都不要包含半角双引号，不要在字符串中换行。
9. 只输出合法 JSON，不要输出任何额外说明。

参考示例：
{few_shot_examples}

禁止写法与修正方向：
{anti_pattern_examples}

逐页内容：
{pages_content}

最终输出必须严格遵循下面的 JSON 结构：
{json_schema}
"""

_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(_SYSTEM_TEMPLATE),
        HumanMessagePromptTemplate.from_template(_HUMAN_TEMPLATE),
    ]
)

_PAGE_ONLY_JSON_SCHEMA_EXAMPLE = """\
{
  "pages": [
    {
      "page_index": 1,
      "script": "<本页中文讲稿>",
      "transition": ""
    }
  ]
}"""

_PAGE_ONLY_HUMAN_TEMPLATE = """\
请只为下面这批页面生成 pages 列表，不要输出 opening，不要输出 closing。

课件 ID：{courseware_id}
学科：{subject}
总页数：{total_pages}
当前批次：第 {chunk_number} 批 / 共 {chunk_count} 批
当前批次页数：{chunk_page_count}

核心要求：
1. 只输出 pages 列表对应的 JSON object，不要输出 opening，不要输出 closing。
2. page_index 必须与当前批次输入一致，顺序必须一致。
3. 每页 script 必须像老师在讲知识点，不要报页码，不要念 PPT，不要念作者、学校、文件名。
4. 页面出现英文时，要优先输出中文解释；必要时可在中文里保留少量英文术语。
5. overview / divider / summary / low_value 页面控制在 1 到 2 句。
6. concept_detail / formula_detail / example_detail / generic 页面控制在 2 到 4 句，要解释知识点本身，不要空泛复述。
7. transition 一律输出空字符串 ""，不要写任何过渡话。
8. 所有字符串值都不要包含半角双引号，不要在字符串中换行。
9. 只输出合法 JSON，不要输出任何额外说明。

参考示例：
{few_shot_examples}

禁止写法与修正方向：
{anti_pattern_examples}

当前批次页面：
{pages_content}

最终输出必须严格遵循下面的 JSON 结构：
{json_schema}
"""

_PAGE_ONLY_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(_SYSTEM_TEMPLATE),
        HumanMessagePromptTemplate.from_template(_PAGE_ONLY_HUMAN_TEMPLATE),
    ]
)

_PAGE_ONLY_RETRY_HUMAN_TEMPLATE = """\
上一轮输出没有通过校验，失败原因：{failure_reason}

请重新生成当前批次页面的 pages JSON，这一次必须严格满足下面的要求：
1. 只能输出一个 JSON object，结构必须是 {{"pages": [ ... ]}}。
2. pages 数组必须严格覆盖这些 page_index，顺序也必须一致：{expected_page_indexes}
3. 每个 script 都要像老师讲知识点，不要报页码，不要说“这一页主要讲的是”“现在我们来看第几页”“下一页继续看”。
4. 页面如果是英文，也必须以中文解释为主，只保留必要术语。
5. 任何一个 script 都不能只是照抄标题、bullet、公式项或英文原句。
6. transition 一律输出空字符串 ""。
7. 所有字符串都必须是单行文本，不能换行，不能包含多余说明。
8. 输出前请先自行检查 JSON 能否被标准 json.loads 解析，但不要输出检查过程。

错误示例：
{anti_pattern_examples}

参考正例：
{few_shot_examples}

当前批次页面：
{pages_content}

最终输出必须严格遵循下面的 JSON 结构：
{json_schema}
"""

_PAGE_ONLY_RETRY_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(_SYSTEM_TEMPLATE),
        HumanMessagePromptTemplate.from_template(_PAGE_ONLY_RETRY_HUMAN_TEMPLATE),
    ]
)

_OVERVIEW_KEYWORDS = (
    "总纲",
    "概览",
    "overview",
    "agenda",
    "outline",
    "目录",
    "contents",
    "课程目标",
    "学习目标",
    "导入",
    "引言",
    "topics",
)
_DIVIDER_KEYWORDS = ("第", "章", "节", "单元", "part", "chapter", "section")
_SUMMARY_KEYWORDS = ("小结", "总结", "回顾", "summary", "review", "结语")
_CONCEPT_KEYWORDS = ("概念", "定义", "特征", "特点", "原理", "结构", "组成", "机制", "layer")
_FORMULA_KEYWORDS = (
    "公式",
    "推导",
    "计算",
    "卷积",
    "步长",
    "padding",
    "stride",
    "output",
    "activation map",
    "parameter",
)
_EXAMPLE_KEYWORDS = ("案例", "示例", "实验", "应用", "example", "demo", "场景")
_DETAIL_PAGE_ROLES = {"concept_detail", "formula_detail", "example_detail", "generic"}

_FORBIDDEN_PHRASES = (
    r"现在我们(?:先)?来看第?\s*\d+\s*页[，,:： ]*",
    r"接下来我们(?:先)?来看第?\s*\d+\s*页[，,:： ]*",
    r"下一页我们继续看[^。！？]*[。！？]?",
    r"我们继续看看下一页[^。！？]*[。！？]?",
    r"这一页(?:主要)?(?:在讲|讲的是|重点是)[，,:： ]*",
    r"建议你重点关注这些关键词[：:]?",
    r"你可以重点留意这些关键词[：:]?",
    r"听这一页时[，,:： ]*",
    r"从页面(?:给出的)?信息看[，,:： ]*",
    r"真正要抓住的是[，,:： ]*",
    r"重点不是逐字去念[^。！？]*[。！？]?",
)

_TITLE_NORMALIZATION_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\btopics\b", re.IGNORECASE), "本节主题"),
    (re.compile(r"\brecall and self-learning\b", re.IGNORECASE), "回顾与自学提示"),
    (re.compile(r"\bupload your answer to\b", re.IGNORECASE), "练习提交提示"),
    (re.compile(r"\bcnn layer\b", re.IGNORECASE), "CNN 各层"),
    (re.compile(r"\bfully connected layer\b", re.IGNORECASE), "全连接层"),
    (re.compile(r"\breminder:\s*fc layer\b", re.IGNORECASE), "全连接层回顾"),
    (re.compile(r"\bconvolution layer:\s*summary\b", re.IGNORECASE), "卷积层小结"),
    (re.compile(r"\bconvolution layer:\s*example\b", re.IGNORECASE), "卷积层例题"),
    (re.compile(r"卷积层[:：]\s*summary", re.IGNORECASE), "卷积层小结"),
    (re.compile(r"卷积层[:：]\s*example", re.IGNORECASE), "卷积层例题"),
    (re.compile(r"^\s*convolution layer\s*$", re.IGNORECASE), "卷积层"),
    (re.compile(r"^\s*convolution\s*$", re.IGNORECASE), "卷积运算"),
    (re.compile(r"\bpooling layer:\s*summary\b", re.IGNORECASE), "池化层小结"),
    (re.compile(r"池化层[:：]\s*summary", re.IGNORECASE), "池化层小结"),
    (re.compile(r"^\s*pooling layer\s*$", re.IGNORECASE), "池化层"),
    (re.compile(r"\bmax pooling\b", re.IGNORECASE), "最大池化"),
    (re.compile(r"\baverage pooling\b", re.IGNORECASE), "平均池化"),
    (re.compile(r"\ba closer look at spatial dimensions\b", re.IGNORECASE), "空间尺寸变化"),
    (re.compile(r"\bin practice\b", re.IGNORECASE), "零填充与尺寸保持"),
    (re.compile(r"\bthe brain/neuron view of\b", re.IGNORECASE), "从神经元视角理解卷积"),
    (re.compile(r"\b1\s*x\s*1\b.*\bconv\b", re.IGNORECASE), "1x1 卷积"),
    (re.compile(r"^\s*1\s+1\s+conv\s*$", re.IGNORECASE), "1x1 卷积"),
]

_NOISE_PATTERNS = (
    r"\b[\w.-]+\.(?:pptx?|pdf|docx?|xlsx?)\b",
    r"\bdr\.?\s+[A-Za-z.\- ]+\b",
    r"\btongji\b",
    r"\bmachine learning\b",
    r"\bshuang liang\b",
    r"\bfigurecopyright[a-z]*\b",
    r"https?://\S+",
)

_TERM_TRANSLATIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bcnn layer\b", re.IGNORECASE), "CNN 各层"),
    (re.compile(r"\bfc layer\b", re.IGNORECASE), "全连接层"),
    (re.compile(r"\bfully connected layer\b", re.IGNORECASE), "全连接层"),
    (re.compile(r"\bconvolution layer\b", re.IGNORECASE), "卷积层"),
    (re.compile(r"\bpooling layer\b", re.IGNORECASE), "池化层"),
    (re.compile(r"\bmax pooling\b", re.IGNORECASE), "最大池化"),
    (re.compile(r"\baverage pooling\b", re.IGNORECASE), "平均池化"),
    (re.compile(r"\btopics\b", re.IGNORECASE), "本节主题"),
    (re.compile(r"\bupload your answer to\b", re.IGNORECASE), "练习提交提示"),
    (re.compile(r"\brecall and self-learning\b", re.IGNORECASE), "回顾与自学提示"),
    (re.compile(r"\bin practice\b", re.IGNORECASE), "实际应用"),
    (re.compile(r"\bthe brain/neuron view of\b", re.IGNORECASE), "从神经元视角看"),
    (re.compile(r"\breminder:\s*fc layer\b", re.IGNORECASE), "全连接层回顾"),
    (re.compile(r"\bactivation map\b", re.IGNORECASE), "激活图"),
    (re.compile(r"\bfeature map\b", re.IGNORECASE), "特征图"),
    (re.compile(r"\breceptive field\b", re.IGNORECASE), "感受野"),
    (re.compile(r"\bpadding\b", re.IGNORECASE), "填充"),
    (re.compile(r"\bstride\b", re.IGNORECASE), "步长"),
    (re.compile(r"\bfilters?\b", re.IGNORECASE), "卷积核"),
    (re.compile(r"\bneuron\b", re.IGNORECASE), "神经元"),
    (re.compile(r"\bconvolution\b", re.IGNORECASE), "卷积"),
    (re.compile(r"\bpooling\b", re.IGNORECASE), "池化"),
    (re.compile(r"\bzero pad(?:ding)?\b", re.IGNORECASE), "零填充"),
    (re.compile(r"\boutput size\b", re.IGNORECASE), "输出尺寸"),
    (re.compile(r"\boutput volume size\b", re.IGNORECASE), "输出体积尺寸"),
    (re.compile(r"\bnumber of parameters\b", re.IGNORECASE), "参数量"),
    (re.compile(r"\binput volume\b", re.IGNORECASE), "输入体积"),
    (re.compile(r"\bcnn\b", re.IGNORECASE), "CNN"),
]


def generate_script(request: ScriptGenerateRequest) -> ScriptGenerateResponse:
    total_pages = len(request.pages)
    logger.info("Script generation started. coursewareId=%s pages=%s", request.courseware_id, total_pages)

    if not settings.LLM_API_KEY:
        logger.warning(
            "LLM API key is missing. Use fallback script. coursewareId=%s pages=%s",
            request.courseware_id,
            total_pages,
        )
        if settings.STRICT_CHAIN:
            raise PythonServiceException(
                "LLM API key is missing in strict chain mode",
                code=THIRD_PARTY_SERVICE_ERROR,
            )
        return build_fallback_script(request)

    raw_output = ""
    try:
        result = refine_script_response(_generate_script_with_llm_chunks(request), request)
        logger.info("Script generation completed. coursewareId=%s pages=%s", request.courseware_id, len(result.pages))
        return result
    except ModelOutputException as exc:
        logger.warning(
            "Model output invalid, fallback applied. coursewareId=%s pages=%s reason=%s preview=%r",
            request.courseware_id,
            total_pages,
            str(exc),
            _truncate_for_log(raw_output),
        )
        if settings.STRICT_CHAIN:
            raise
    except AppException as exc:
        logger.warning(
            "Script generation degraded to fallback. coursewareId=%s pages=%s code=%s",
            request.courseware_id,
            total_pages,
            exc.code,
        )
        if settings.STRICT_CHAIN:
            raise
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected script generation failure. coursewareId=%s pages=%s", request.courseware_id, total_pages)
        if settings.STRICT_CHAIN:
            raise PythonServiceException(
                "script generation failed in strict chain mode",
                code=THIRD_PARTY_SERVICE_ERROR,
            )

    return build_fallback_script(request)


def extract_json_payload(raw_output: str) -> str:
    stripped = (raw_output or "").strip()
    if not stripped:
        return stripped

    fenced_match = re.search(r"```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)```", stripped)
    if fenced_match:
        fenced_content = fenced_match.group(1).strip()
        return _extract_first_json_object(fenced_content) or fenced_content

    return _extract_first_json_object(stripped) or stripped


def parse_model_output(raw_output: str, request: ScriptGenerateRequest) -> ScriptGenerateResponse:
    response, _ = _parse_model_output_with_details(raw_output, request)
    return response


def _parse_model_output_with_details(
    raw_output: str,
    request: ScriptGenerateRequest,
) -> tuple[ScriptGenerateResponse, dict[int, str]]:
    data = _load_json_like_payload(extract_json_payload(raw_output))
    if not isinstance(data, dict):
        raise ModelOutputException("模型输出的顶层 JSON 必须是 object")

    raw_page_scripts = _extract_raw_page_scripts(data.get("pages"))
    normalized = _normalize_model_response_data(data, raw_page_scripts, request)
    try:
        return ScriptGenerateResponse(**normalized), raw_page_scripts
    except ValidationError as exc:
        raise ModelOutputException("模型输出字段校验失败") from exc


def build_fallback_script(request: ScriptGenerateRequest) -> ScriptGenerateResponse:
    page_scripts: list[PageScript] = []

    for page in request.pages:
        page_role = _infer_page_role(page.title, page.text_content, page.keywords)
        page_scripts.append(
            PageScript(
                page_index=page.page_index,
                script=_build_role_aware_fallback_script(
                    title=page.title,
                    text_content=page.text_content,
                    keywords=page.keywords,
                    page_role=page_role,
                ),
                transition="",
            )
        )

    response = ScriptGenerateResponse(
        courseware_id=request.courseware_id,
        opening=_build_opening(request),
        pages=page_scripts,
        closing=_build_closing(request),
    )
    logger.info("Fallback script built. coursewareId=%s pages=%s", request.courseware_id, len(response.pages))
    return response


def refine_script_response(response: ScriptGenerateResponse, request: ScriptGenerateRequest) -> ScriptGenerateResponse:
    source_pages = {page.page_index: page for page in request.pages}
    refined_pages: list[PageScript] = []

    for page_script in response.pages:
        source_page = source_pages.get(page_script.page_index)
        if source_page is None:
            refined_pages.append(PageScript(page_index=page_script.page_index, script=_clean_text(page_script.script), transition=""))
            continue

        page_role = _infer_page_role(source_page.title, source_page.text_content, source_page.keywords)
        refined_script = _refine_teacher_style_script(
            page_script.script,
            title=source_page.title,
            text_content=source_page.text_content,
            keywords=source_page.keywords,
            page_role=page_role,
        )
        refined_pages.append(
            PageScript(
                page_index=page_script.page_index,
                script=refined_script,
                transition="",
            )
        )

    opening = _clean_opening_or_closing(response.opening, fallback=_build_opening(request))
    closing = _clean_opening_or_closing(response.closing, fallback=_build_closing(request))
    return ScriptGenerateResponse(
        courseware_id=response.courseware_id,
        opening=opening,
        pages=refined_pages,
        closing=closing,
    )


def _generate_script_with_llm_chunks(request: ScriptGenerateRequest) -> ScriptGenerateResponse:
    page_chunks = _chunk_pages(request.pages, SCRIPT_PAGE_CHUNK_SIZE)
    generated_pages: list[PageScript] = []
    llm_client = get_llm_client()

    for chunk_index, chunk_pages in enumerate(page_chunks, start=1):
        generated_pages.extend(
            _generate_chunk_pages(
                llm_client=llm_client,
                root_request=request,
                chunk_pages=chunk_pages,
                chunk_label=str(chunk_index),
                root_chunk_count=len(page_chunks),
            )
        )

    return ScriptGenerateResponse(
        courseware_id=request.courseware_id,
        opening=_build_opening(request),
        pages=generated_pages,
        closing=_build_closing(request),
    )


def _generate_chunk_pages(
    *,
    llm_client: Any,
    root_request: ScriptGenerateRequest,
    chunk_pages: list[Any],
    chunk_label: str,
    root_chunk_count: int,
) -> list[PageScript]:
    chunk_request = ScriptGenerateRequest(
        courseware_id=root_request.courseware_id,
        courseware_name=root_request.courseware_name,
        subject=root_request.subject,
        pages=chunk_pages,
    )
    last_error = "unknown"

    for attempt in range(1, SCRIPT_CHUNK_RETRY_ATTEMPTS + 1):
        try:
            raw_output = _invoke_chunk_llm(
                llm_client=llm_client,
                root_request=root_request,
                chunk_request=chunk_request,
                chunk_label=chunk_label,
                root_chunk_count=root_chunk_count,
                attempt=attempt,
                failure_reason=last_error,
            )
            chunk_response, raw_page_scripts = _parse_model_output_with_details(raw_output, chunk_request)
            _ensure_chunk_quality(chunk_response, raw_page_scripts, chunk_request)
            logger.info(
                "Script chunk generated. coursewareId=%s chunk=%s/%s pages=%s attempt=%s",
                root_request.courseware_id,
                chunk_label,
                root_chunk_count,
                len(chunk_response.pages),
                attempt,
            )
            return chunk_response.pages
        except ModelOutputException as exc:
            last_error = str(exc)
            logger.warning(
                "Script chunk invalid. coursewareId=%s chunk=%s/%s attempt=%s reason=%s",
                root_request.courseware_id,
                chunk_label,
                root_chunk_count,
                attempt,
                last_error,
            )

    if len(chunk_pages) > 1:
        left_pages, right_pages = _split_page_chunk(chunk_pages)
        logger.info(
            "Script chunk split for retry. coursewareId=%s chunk=%s/%s left=%s right=%s lastReason=%s",
            root_request.courseware_id,
            chunk_label,
            root_chunk_count,
            len(left_pages),
            len(right_pages),
            last_error,
        )
        combined_pages: list[PageScript] = []
        combined_pages.extend(
            _generate_chunk_pages(
                llm_client=llm_client,
                root_request=root_request,
                chunk_pages=left_pages,
                chunk_label=f"{chunk_label}.1",
                root_chunk_count=root_chunk_count,
            )
        )
        combined_pages.extend(
            _generate_chunk_pages(
                llm_client=llm_client,
                root_request=root_request,
                chunk_pages=right_pages,
                chunk_label=f"{chunk_label}.2",
                root_chunk_count=root_chunk_count,
            )
        )
        return combined_pages

    logger.warning(
        "Script chunk degraded to fallback. coursewareId=%s chunk=%s/%s reason=%s",
        root_request.courseware_id,
        chunk_label,
        root_chunk_count,
        last_error,
    )
    return build_fallback_script(chunk_request).pages


def _invoke_chunk_llm(
    *,
    llm_client: Any,
    root_request: ScriptGenerateRequest,
    chunk_request: ScriptGenerateRequest,
    chunk_label: str,
    root_chunk_count: int,
    attempt: int,
    failure_reason: str,
) -> str:
    prompt_template = _PAGE_ONLY_PROMPT_TEMPLATE if attempt == 1 else _PAGE_ONLY_RETRY_PROMPT_TEMPLATE
    prompt_messages = prompt_template.format_messages(
        courseware_id=root_request.courseware_id,
        subject=_resolve_subject(root_request.subject),
        total_pages=len(root_request.pages),
        chunk_number=chunk_label,
        chunk_count=root_chunk_count,
        chunk_page_count=len(chunk_request.pages),
        pages_content=_format_pages_content(chunk_request),
        few_shot_examples=_FEW_SHOT_EXAMPLES,
        anti_pattern_examples=_ANTI_PATTERN_EXAMPLES,
        failure_reason=failure_reason,
        expected_page_indexes=_format_expected_page_indexes(chunk_request.pages),
        json_schema=_PAGE_ONLY_JSON_SCHEMA_EXAMPLE,
    )
    return (
        llm_client.invoke(
            prompt_messages,
            temperature=SCRIPT_TEMPERATURE,
            max_tokens=SCRIPT_PAGE_MAX_TOKENS,
        )
        or ""
    )


def _format_expected_page_indexes(pages: list[Any]) -> str:
    return "[" + ", ".join(str(page.page_index) for page in pages) + "]"


def _split_page_chunk(chunk_pages: list[Any]) -> tuple[list[Any], list[Any]]:
    if len(chunk_pages) < 2:
        raise ValueError("chunk_pages must contain at least 2 items to split")
    middle = max(1, len(chunk_pages) // 2)
    return chunk_pages[:middle], chunk_pages[middle:]


def _format_pages_content(request: ScriptGenerateRequest) -> str:
    total_pages = len(request.pages)
    lines: list[str] = []
    for page in request.pages:
        page_role = _infer_page_role(page.title, page.text_content, page.keywords)
        normalized_title = _normalize_topic_label(page.title, page.text_content)
        lines.append(f"--- page {page.page_index} / {total_pages} ---")
        lines.append(f"title: {normalized_title or _resolve_title(page.title, page.page_index)}")
        lines.append(f"page_role: {page_role}")
        lines.append(f"teacher_goal: {_narration_guidance_for_role(page_role, normalized_title)}")
        lines.append(f"keywords: {_format_keywords(page.keywords)}")
        lines.append(f"clean_text: {_prepare_slide_text(page.text_content) or '（本页文字较少）'}")
        if page.visual_summary:
            lines.append(f"visual_summary: {_clean_text(page.visual_summary)}")
        if page.visual_objects:
            cleaned_objects = [_clean_text(item) for item in page.visual_objects if _clean_text(item)]
            if cleaned_objects:
                lines.append(f"visual_objects: {'、'.join(cleaned_objects)}")
        lines.append("")
    return "\n".join(lines).strip()


def _chunk_pages(pages: list[Any], chunk_size: int) -> list[list[Any]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    return [pages[index : index + chunk_size] for index in range(0, len(pages), chunk_size)]


def _extract_raw_page_scripts(raw_pages: Any) -> dict[int, str]:
    if not isinstance(raw_pages, list) or not raw_pages:
        raise ModelOutputException("模型输出缺少有效的 pages 列表")

    pages_by_index: dict[int, str] = {}
    for page in raw_pages:
        if not isinstance(page, dict):
            continue
        try:
            page_index = _parse_page_index(page.get("page_index"))
        except ModelOutputException:
            continue
        script = _clean_text(str(page.get("script", "")))
        if script:
            pages_by_index[page_index] = script
    return pages_by_index


def _normalize_model_response_data(
    data: dict[str, Any],
    pages_by_index: dict[int, str],
    request: ScriptGenerateRequest,
) -> dict[str, Any]:
    normalized_pages: list[dict[str, Any]] = []
    for source_page in request.pages:
        raw_script = pages_by_index.get(source_page.page_index)
        if raw_script:
            script_text = raw_script
        else:
            script_text = _build_role_aware_fallback_script(
                title=source_page.title,
                text_content=source_page.text_content,
                keywords=source_page.keywords,
                page_role=_infer_page_role(source_page.title, source_page.text_content, source_page.keywords),
            )

        normalized_pages.append(
            {
                "page_index": source_page.page_index,
                "script": script_text,
                "transition": "",
            }
        )

    opening = _clean_text(str(data.get("opening", ""))) or _build_opening(request)
    closing = _clean_text(str(data.get("closing", ""))) or _build_closing(request)
    return {
        "courseware_id": request.courseware_id,
        "opening": opening,
        "pages": normalized_pages,
        "closing": closing,
    }


def _ensure_chunk_quality(
    response: ScriptGenerateResponse,
    raw_page_scripts: dict[int, str],
    request: ScriptGenerateRequest,
) -> None:
    missing_pages = [page.page_index for page in request.pages if page.page_index not in raw_page_scripts]
    if len(missing_pages) >= max(1, len(request.pages) // 2):
        raise ModelOutputException(f"模型漏写页面过多: {missing_pages}")

    quality_issues: list[str] = []
    low_quality_count = 0
    for page in request.pages:
        raw_script = raw_page_scripts.get(page.page_index, "")
        issue = _script_quality_issue(
            raw_script,
            title=page.title,
            text_content=page.text_content,
            keywords=page.keywords,
            page_role=_infer_page_role(page.title, page.text_content, page.keywords),
        )
        if issue:
            low_quality_count += 1
            quality_issues.append(f"{page.page_index}:{issue}")

    if len(request.pages) == 1 and quality_issues:
        raise ModelOutputException(f"单页讲稿质量不足: {quality_issues[0]}")

    if low_quality_count >= max(1, len(request.pages) // 2):
        raise ModelOutputException("本批次讲稿质量不足: " + " | ".join(quality_issues[:4]))

    expected_indexes = [page.page_index for page in request.pages]
    actual_indexes = [page.page_index for page in response.pages]
    if actual_indexes != expected_indexes:
        raise ModelOutputException(f"页码顺序不一致: expected={expected_indexes} actual={actual_indexes}")


def _script_quality_issue(
    script: str,
    *,
    title: str | None,
    text_content: str,
    keywords: list[str],
    page_role: str,
) -> str:
    normalized = _clean_text(script)
    if not normalized:
        return "script empty"
    if _contains_forbidden_phrase(normalized):
        return "contains filler phrasing"
    if _is_mostly_english(normalized):
        return "mostly english"
    if _looks_like_slide_reading(normalized, text_content):
        return "too close to slide text"
    if page_role in {"formula_detail", "example_detail"} and len(normalized) < 24:
        return "too short for detail page"
    if page_role in {"overview", "divider", "summary"} and len(normalized) > 150:
        return "too verbose for overview page"
    if not _contains_enough_chinese(normalized):
        return "insufficient chinese explanation"

    fallback = _build_role_aware_fallback_script(title, text_content, keywords, page_role)
    if fallback and normalized == fallback:
        return "fell back to template explanation"
    return ""


def _load_json_like_payload(raw_output: str) -> Any:
    repaired_payload = _repair_common_json_issues(raw_output)
    try:
        return json.loads(repaired_payload)
    except json.JSONDecodeError:
        pass

    python_like = repaired_payload
    python_like = re.sub(r"\bnull\b", "None", python_like)
    python_like = re.sub(r"\btrue\b", "True", python_like, flags=re.IGNORECASE)
    python_like = re.sub(r"\bfalse\b", "False", python_like, flags=re.IGNORECASE)
    try:
        return ast.literal_eval(python_like)
    except (ValueError, SyntaxError) as exc:
        raise ModelOutputException("模型输出不是合法 JSON") from exc


def _parse_page_index(raw_value: Any) -> int:
    try:
        page_index = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ModelOutputException("模型输出中的 page_index 必须是正整数") from exc

    if page_index <= 0:
        raise ModelOutputException("模型输出中的 page_index 必须是正整数")
    return page_index


def _extract_first_json_object(text: str) -> str | None:
    start_index = -1
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if start_index < 0:
            if char == "{":
                start_index = index
                depth = 1
            continue

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1].strip()

    return None


def _repair_common_json_issues(text: str) -> str:
    repaired = (text or "").strip()
    repaired = repaired.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    repaired = repaired.replace("\ufeff", "")
    repaired = _escape_control_chars_in_json_strings(repaired)
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    return repaired


def _escape_control_chars_in_json_strings(text: str) -> str:
    if not text:
        return text

    result: list[str] = []
    in_string = False
    escaped = False

    for char in text:
        if in_string:
            if escaped:
                result.append(char)
                escaped = False
                continue

            if char == "\\":
                result.append(char)
                escaped = True
                continue

            if char == '"':
                result.append(char)
                in_string = False
                continue

            if char == "\n":
                result.append("\\n")
                continue
            if char == "\r":
                result.append("\\r")
                continue
            if char == "\t":
                result.append("\\t")
                continue

            result.append(char)
            continue

        result.append(char)
        if char == '"':
            in_string = True

    return "".join(result)


def _truncate_for_log(raw_output: str, limit: int = 240) -> str:
    normalized = (raw_output or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def _resolve_subject(subject: str | None) -> str:
    normalized = _clean_text(subject or "")
    return normalized or "通用课程"


def _resolve_title(title: str | None, page_index: int) -> str:
    normalized = _normalize_topic_label(title, title or "")
    return normalized or f"第 {page_index} 页重点"


def _format_keywords(keywords: list[str]) -> str:
    cleaned: list[str] = []
    for keyword in keywords:
        normalized = _humanize_label(keyword)
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    if not cleaned:
        return "本页核心概念"
    return "、".join(cleaned[:6])


def _clean_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _prepare_slide_text(text: str, limit: int = 180) -> str:
    normalized = _clean_text(text)
    normalized = _strip_noise_fragments(normalized)
    normalized = _translate_common_terms(normalized)
    normalized = normalized.replace('"', "").replace("'", "")
    normalized = re.sub(r"\s+", " ", normalized).strip(" -;:,.，。；：")
    return normalized if len(normalized) <= limit else normalized[:limit].rstrip() + "..."


def _infer_page_role(title: str | None, text_content: str, keywords: list[str]) -> str:
    combined = " ".join(
        [
            _clean_text(title or "").lower(),
            _clean_text(text_content).lower(),
            " ".join(_clean_text(keyword).lower() for keyword in keywords),
        ]
    )

    if _has_any_keyword(combined, _OVERVIEW_KEYWORDS):
        return "overview"
    if _has_any_keyword(combined, _SUMMARY_KEYWORDS):
        return "summary"
    if _looks_like_divider_page(title, text_content):
        return "divider"
    if _has_any_keyword(combined, _FORMULA_KEYWORDS):
        return "formula_detail"
    if _has_any_keyword(combined, _EXAMPLE_KEYWORDS):
        return "example_detail"
    if _has_any_keyword(combined, _CONCEPT_KEYWORDS):
        return "concept_detail"
    return "generic"


def _has_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _looks_like_divider_page(title: str | None, text_content: str) -> bool:
    normalized_title = _clean_text(title or "")
    normalized_text = _clean_text(text_content)
    short_title = bool(normalized_title) and len(normalized_title) <= 18
    short_text = len(normalized_text) <= 36
    mentions_section = _has_any_keyword(normalized_title.lower(), _DIVIDER_KEYWORDS)
    return short_title and short_text and mentions_section


def _narration_guidance_for_role(page_role: str, topic: str | None = None) -> str:
    if topic == "练习提交提示":
        return "这是练习提示页，只做简短说明。"
    if topic == "回顾与自学提示":
        return "这是学习提醒页，不展开新知识。"
    if page_role == "overview":
        return "先搭框架，只讲本节要点和结构，不展开细节。"
    if page_role == "divider":
        return "这是分隔页或章节页，只做非常简短的导入。"
    if page_role == "summary":
        return "回收前面内容，讲清楚几条结论怎么串起来。"
    if page_role == "concept_detail":
        return "把概念讲明白，强调定义、作用、结构和关系。"
    if page_role == "formula_detail":
        return "把公式或计算关系讲清楚，重点说明变量和结果的关系。"
    if page_role == "example_detail":
        return "用页面里的例子帮助理解前面的概念，不要空泛。"
    return "围绕页面内容做中文化解释，重点讲知识点，不要照读。"


def _build_role_aware_fallback_script(
    title: str | None,
    text_content: str,
    keywords: list[str],
    page_role: str,
) -> str:
    topic = _normalize_topic_label(title, text_content) or _primary_topic(title, keywords, text_content)
    specific = _page_specific_explanation(topic, text_content, page_role)
    if specific:
        return specific

    chinese_fact = _extract_chinese_fact(text_content)
    if topic == "练习提交提示":
        return "这一页是练习或提交提示，本身不承载新的知识点，知道需要按要求完成对应练习即可。"
    if topic == "回顾与自学提示":
        return "这一页更像学习提醒，不是在引入新的知识点。可以把它理解成提示我们先回顾前置基础，再带着问题进入后面的正式内容。"

    if page_role == "overview":
        return _join_non_empty(
            [
                f"{topic}这一部分可以先抓整体结构。" if topic else "这部分内容可以先抓整体结构。",
                "重点是先分清几个核心部分分别负责什么，再看它们怎样配合起来完成整套流程。",
            ]
        )

    if page_role == "divider":
        return _join_non_empty(
            [
                f"{topic}这一部分的重点，是先把主线和核心问题抓住。" if topic else "这一部分的重点，是先把主线和核心问题抓住。",
                "先明确它解决什么问题，再去看后面的具体细节。",
            ]
        )

    if page_role == "summary":
        return _join_non_empty(
            [
                f"{topic}这里可以收束为几条关键结论。" if topic else "这里可以把前面的内容收束为几条关键结论。",
                "重点不是重复细枝末节，而是把几个核心概念和它们之间的关系重新串起来。",
            ]
        )

    if chinese_fact:
        if page_role == "formula_detail":
            return _join_non_empty(
                [
                    f"这里重点理解{topic}相关的计算关系。" if topic else "这里重点理解本页涉及的计算关系。",
                    chinese_fact,
                    "真正需要记住的是已知条件、计算过程和最后结果之间怎样对应起来。",
                ]
            )
        return _join_non_empty(
            [
                f"这里重点讲{topic}。" if topic else "这里重点讲本页的核心知识点。",
                chinese_fact,
                "可以把它放回整节内容里理解，重点看它解决什么问题，以及和前后内容怎样衔接。",
            ]
        )

    if page_role == "formula_detail":
        return _join_non_empty(
            [
                f"这里重点理解{topic}相关的计算关系。" if topic else "这里重点理解本页涉及的计算关系。",
                "不要只停留在公式表面，更要看输入规模、参数设置和输出结果之间怎样对应。",
            ]
        )

    if page_role == "example_detail":
        return _join_non_empty(
            [
                f"这里用一个具体例子来说明{topic}怎样落到实际计算里。" if topic else "这里用一个具体例子来说明前面讲过的概念怎样落到实际计算里。",
                "把已知条件、推导步骤和最后结论连起来看，会比单独记数字更容易真正理解。",
            ]
        )

    return _join_non_empty(
        [
            f"{topic}的关键，不在于把页面文字重复一遍，而在于看清它解决什么问题。" if topic else "本页的关键，不在于把页面文字重复一遍，而在于看清它解决什么问题。",
            "要点是先弄清它在整体流程里负责什么，再看它和前后模块怎样配合。",
        ]
    )


def _page_specific_explanation(topic: str, text_content: str, page_role: str) -> str:
    normalized_topic = _clean_text(topic)
    if not normalized_topic:
        return ""

    raw_lower = _clean_text(text_content).lower()
    lowered = _prepare_slide_text(text_content, limit=320).lower()

    if normalized_topic == "本节主题":
        return (
            "这一部分先把本节内容的整体框架搭起来。"
            "可以先把卷积神经网络理解成由若干功能不同的层协同完成特征提取与分类的结构，"
            "后面再分别展开卷积层、池化层和全连接层各自的作用。"
        )
    if normalized_topic == "回顾与自学提示":
        return "这一页更像学习提醒，不是在引入新的知识点。它的作用是帮助我们先回顾前置基础，再带着问题进入后面的正式内容。"
    if normalized_topic == "练习提交提示":
        return "这一页是练习或提交提示，本身不承载新的知识点，知道需要按要求完成对应练习即可。"
    if normalized_topic == "CNN 各层":
        return (
            "这里先把卷积神经网络里几类核心层的分工理清楚。"
            "卷积层负责提取局部特征，池化层负责压缩表示和增强稳定性，全连接层负责综合特征并输出最终判断。"
        )
    if normalized_topic in {"全连接层", "全连接层回顾"}:
        return (
            "这里重点理解全连接层怎样把前面提取到的特征送入分类器。"
            "核心做法是先把多维特征拉平成一维向量，再让每个输出神经元和全部输入相连，"
            "从而综合所有特征做最后判断。"
        )
    if normalized_topic == "卷积层":
        if "preserve spatial structure" in lowered:
            return "这里是在说明卷积层和全连接层的一个重要区别。卷积层不会先把图像拉平，而是保留原来的空间结构，因此更适合处理图像里的局部模式。"
        if "6 separate" in lowered or "28x28x6" in lowered or "activation maps" in lowered:
            return "这里重点理解为什么多个卷积核会产生多张特征图。每个卷积核都会关注输入中的一种模式，最后把不同卷积核得到的特征图沿深度方向堆叠起来，就形成新的输出体积。"
        if "dot product" in lowered or "5x5x3" in lowered:
            return "这里重点理解卷积层怎样在局部区域上提取特征。卷积核会在输入上逐位置滑动，每到一个位置都和局部区域做点积，由此得到新的响应值，并最终组成特征图。"
        return "这里重点理解卷积层的基本工作方式。核心是局部连接和参数共享，也就是用同一组卷积核在不同位置重复提取局部特征。"
    if normalized_topic == "卷积运算":
        if "stride=2" in lowered or "if stride=2" in lowered:
            return "这里是在对比不同步长下卷积窗口的移动方式。步长越大，卷积核跨得越快，输出特征图就越小，同时也会损失一部分细粒度的位置变化。"
        if "stride=1" in lowered:
            return "这里是在用矩阵例子说明卷积怎样逐位置计算。步长为 1 时，卷积核会紧密地在输入上滑动，因此输出会保留更多空间细节。"
        return "这里通过一个具体矩阵例子帮助理解卷积运算本身。核心是卷积核与局部区域逐元素相乘再求和，从而把原始像素变成更有意义的局部特征。"
    if normalized_topic == "空间尺寸变化":
        if "cannot apply" in lowered or "2.33" in lowered:
            return "这里要说明输出尺寸不是随便都会得到整数。输入大小、卷积核大小和步长必须彼此匹配，否则卷积窗口就不能完整覆盖输入，计算结果也不成立。"
        if "stride 2" in lowered and "3x3 output" in lowered:
            return "这一页是在比较步长变化对输出尺寸的影响。同样是 7x7 输入和 3x3 卷积核，步长从 1 增大到 2 之后，输出会从 5x5 进一步缩小到 3x3。"
        if "5x5 output" in lowered:
            return "这里是在演示最基本的输出尺寸变化。7x7 输入在不填充、步长为 1 的情况下，使用 3x3 卷积核计算后，会得到 5x5 的输出。"
        if "activation map" in lowered:
            return "这里先从最直观的角度理解特征图的空间尺寸。卷积核在输入图像上逐位置滑动，每次得到一个响应值，这些响应按空间位置排开以后，就形成新的特征图。"
        return "这里重点理解卷积层的空间尺寸为什么会变化。不要只记公式结果，更要看输入大小、卷积核大小、步长和填充怎样共同决定输出。"
    if normalized_topic == "零填充与尺寸保持":
        if "7x7 output" in lowered or "pad with 1 pixel border" in lowered:
            return "这里是在说明零填充为什么常用。给输入外围补上一圈零以后，再配合 3x3 卷积核和步长 1 计算，就能把输出空间尺寸保持住，不会越卷越小。"
        return "这里重点理解零填充的作用。它一方面能保留边缘信息，另一方面也能配合卷积核大小和步长，把输出尺寸控制在更合适的范围。"
    if normalized_topic == "卷积层例题":
        if "number of parameters" in raw_lower or "params" in raw_lower or "参数量" in lowered:
            return "这里是在计算卷积层的参数量。先看单个卷积核有多少参数，也就是卷积核宽高乘以输入通道数，再加上一个偏置；然后再乘以卷积核个数，就得到整层参数量。"
        if (
            "output volume size" in raw_lower
            or "output size" in raw_lower
            or "输出体积尺寸" in lowered
            or "输出尺寸" in lowered
        ):
            return "这里是在练习卷积层输出尺寸的计算。关键不是把数字逐个念出来，而是先分清输入大小、卷积核大小、步长和填充分别影响什么，再据此判断空间尺寸和通道数怎样变化。"
        if "shrinks volumes spatially" in lowered:
            return "这里用连续卷积的例子说明，如果不做合适的填充，特征图的空间尺寸会一层层缩小得很快。实际设计网络时，往往要通过填充和步长控制这种缩小速度。"
        return "这里是卷积层的例题页，重点要把题目给出的输入尺寸、卷积核设置和最后结果连起来看，真正理解每个超参数在计算里起什么作用。"
    if normalized_topic == "卷积层小结":
        if "hyperparameters" in lowered or "common settings" in lowered:
            return "这里是在总结卷积层最常见的几个超参数。卷积核大小、步长、填充和卷积核个数会一起决定输出尺寸、感受野以及参数规模，是设计卷积层时最核心的控制量。"
        if "parameter sharing" in lowered:
            return "这里强调的是卷积层为什么参数更省。因为同一个卷积核会在不同位置重复使用，所以参数共享能显著减少需要学习的权重，同时保留空间结构。"
        return "这里是在回收卷积层的核心结论。要点是把卷积层的计算方式、超参数含义以及参数共享带来的优势放在一起理解。"
    if normalized_topic == "1x1 卷积":
        return "这里要理解 1x1 卷积并不是没有意义，而是在每个空间位置上重新组合通道信息。它不会扩大空间感受野，但非常适合做通道压缩、通道扩展或特征融合。"
    if normalized_topic == "从神经元视角理解卷积":
        if "receptive field" in lowered:
            return "这里是在强调卷积层的感受野概念。每个输出位置只连接输入中的一个局部区域，这个局部区域就是它的感受野，而不同位置之间共享同一组参数。"
        if "3d grid" in lowered or "5 filters" in lowered:
            return "这里要把卷积层看成一个三维的神经元网格。空间上的两个维度对应位置变化，深度方向对应不同卷积核产生的不同特征图。"
        if "local connectivity" in lowered:
            return "这里换了一个神经元的视角去理解卷积层。卷积层不是所有神经元都连接全部输入，而是每个神经元只看局部区域，这就是局部连接。"
        return "这里是在强调卷积层的两个核心特点：局部连接和参数共享。也正因为这样，卷积层既能抓住局部模式，又不会像全连接那样带来过多参数。"
    if normalized_topic == "池化层":
        return "这里重点理解池化层为什么能让表示更小、更稳定。它会对每张特征图独立做下采样，在压缩空间尺寸的同时，尽量保留最重要的响应。"
    if normalized_topic == "最大池化":
        return "这里重点理解最大池化怎样工作。它会在每个池化窗口里只保留响应最大的那个值，因此更强调最显著的局部特征。"
    if normalized_topic == "平均池化":
        return "这里重点理解平均池化怎样工作。它会对池化窗口里的值做平均，因此得到的表示会更平滑，也更偏向整体趋势。"
    if normalized_topic == "池化层小结":
        return "这里是在总结池化层最常见的设置。通常会看到窗口大小和步长一起控制下采样幅度，而且池化层本身没有可学习参数，它的作用是压缩空间尺寸、保留主要响应。"

    if page_role == "formula_detail" and "output size" in lowered:
        return "这里重点理解输出尺寸怎样由输入大小、卷积核大小、步长和填充共同决定。真正需要掌握的是这些量之间的对应关系，而不是把公式孤立地背下来。"
    return ""


def _refine_teacher_style_script(
    script: str,
    title: str | None,
    text_content: str,
    keywords: list[str],
    page_role: str,
) -> str:
    normalized = _clean_text(script).replace('"', "")
    normalized = _remove_forbidden_phrases(normalized)
    normalized = _strip_noise_fragments(normalized)
    normalized = _translate_common_terms(normalized)
    normalized = _clean_text(normalized)

    if _needs_teacher_style_rewrite(normalized) or _looks_like_slide_reading(normalized, text_content):
        normalized = _build_role_aware_fallback_script(title, text_content, keywords, page_role)

    if page_role in {"overview", "divider", "summary"}:
        normalized = _shorten_overview_script(normalized)
    else:
        normalized = _expand_detail_script(normalized, title, text_content, keywords, page_role)

    normalized = _remove_forbidden_phrases(normalized)
    normalized = _smooth_teacher_tone(normalized)
    normalized = _clean_text(normalized)
    return normalized


def _shorten_overview_script(script: str) -> str:
    sentences = _split_sentences(script)
    if not sentences:
        return script
    concise = " ".join(sentences[:2])
    return _truncate_sentence(concise, 110)


def _expand_detail_script(
    script: str,
    title: str | None,
    text_content: str,
    keywords: list[str],
    page_role: str,
) -> str:
    min_length = 24 if page_role in {"formula_detail", "example_detail"} else 18
    if (
        len(script) >= min_length
        and _contains_enough_chinese(script)
        and not _is_mostly_english(script)
        and not _looks_like_slide_reading(script, text_content)
        and not _contains_forbidden_phrase(script)
    ):
        return _truncate_sentence(script, 220)

    fallback = _build_role_aware_fallback_script(title, text_content, keywords, page_role)
    return _truncate_sentence(fallback, 220)


def _split_sentences(text: str) -> list[str]:
    normalized = _clean_text(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[。！？!?])\s*", normalized)
    return [part.strip() for part in parts if part.strip()]


def _truncate_sentence(text: str, limit: int) -> str:
    normalized = _clean_text(text)
    if len(normalized) <= limit:
        return normalized
    shortened = normalized[:limit].rstrip(" ，,;；:：")
    if shortened.endswith(("。", "！", "？")):
        return shortened
    return shortened + "。"


def _join_non_empty(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if _clean_text(part))


def _build_opening(request: ScriptGenerateRequest) -> str:
    theme = _infer_course_theme(request)
    if theme == "卷积神经网络各层":
        return "这节内容重点梳理卷积神经网络里几类核心层的作用、结构和计算逻辑，尤其要分清卷积、池化和全连接之间的关系。"
    if theme:
        return f"这节内容重点梳理{theme}相关的核心知识点，尽量把概念、关系和计算逻辑讲清楚。"
    return "这节内容重点梳理本课件里的核心知识点，尽量把概念、关系和计算逻辑讲清楚。"


def _build_closing(request: ScriptGenerateRequest) -> str:
    theme = _infer_course_theme(request)
    if theme:
        return f"关于{theme}的核心思路先梳理到这里，后面可以再把关键概念、计算关系和典型场景连起来复习。"
    return "这部分核心内容先梳理到这里，后面可以再把关键概念、计算关系和典型场景连起来复习。"


def _infer_course_theme(request: ScriptGenerateRequest) -> str:
    normalized_titles: list[str] = []
    for page in request.pages[:8]:
        title = _normalize_topic_label(page.title, page.text_content)
        if title and title not in normalized_titles:
            normalized_titles.append(title)

    cnn_related = {"CNN 各层", "卷积层", "卷积层例题", "卷积层小结", "池化层", "池化层小结", "全连接层", "全连接层回顾"}
    if any(title in cnn_related for title in normalized_titles):
        return "卷积神经网络各层"

    for title in normalized_titles:
        if title not in {"本节主题", "回顾与自学提示", "练习提交提示"}:
            return title

    first_page = request.pages[0] if request.pages else None
    if first_page is None:
        return ""
    fallback = _normalize_topic_label(first_page.title, first_page.text_content)
    if fallback:
        return fallback
    for keyword in first_page.keywords:
        cleaned = _humanize_label(keyword)
        if cleaned:
            return cleaned
    return ""


def _clean_opening_or_closing(text: str, fallback: str) -> str:
    normalized = _remove_forbidden_phrases(_translate_common_terms(_clean_text(text))).replace('"', "")
    if not normalized or not _contains_enough_chinese(normalized) or len(normalized) < 12:
        return fallback
    return _truncate_sentence(normalized, 90)


def _remove_forbidden_phrases(text: str) -> str:
    cleaned = text
    for pattern in _FORBIDDEN_PHRASES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("这一页", "").replace("本页主要", "").strip(" ，,。；;")
    return _clean_text(cleaned)


def _contains_forbidden_phrase(text: str) -> bool:
    lowered = _clean_text(text).lower()
    return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in _FORBIDDEN_PHRASES)


def _strip_noise_fragments(text: str) -> str:
    cleaned = text
    for pattern in _NOISE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,})+\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _translate_common_terms(text: str) -> str:
    translated = text
    for pattern, replacement in _TERM_TRANSLATIONS:
        translated = pattern.sub(replacement, translated)
    return translated


def _primary_topic(title: str | None, keywords: list[str], text_content: str) -> str:
    title_label = _normalize_topic_label(title, text_content)
    if title_label and not _is_noise_term(title_label):
        return title_label

    for keyword in keywords:
        keyword_label = _humanize_label(keyword)
        if keyword_label and not _is_noise_term(keyword_label):
            return keyword_label

    chinese_fact = _extract_chinese_fact(text_content)
    if chinese_fact:
        return _truncate_sentence(chinese_fact, 24).rstrip("。")
    return ""


def _humanize_label(text: str) -> str:
    normalized = _clean_text(text)
    normalized = _strip_noise_fragments(normalized)
    normalized = _translate_common_terms(normalized)
    normalized = normalized.replace('"', "").replace("'", "")
    normalized = re.sub(r"^[\-–—:：]+|[\-–—:：]+$", "", normalized).strip()
    return normalized


def _normalize_topic_label(title: str | None, text_content: str) -> str:
    candidates = [title or "", _prepare_slide_text(text_content, limit=120)]
    for candidate in candidates:
        raw_candidate = _clean_text(candidate)
        normalized_candidate = _humanize_label(candidate)
        for probe in (raw_candidate, normalized_candidate):
            if not probe:
                continue
            for pattern, replacement in _TITLE_NORMALIZATION_RULES:
                if pattern.search(probe):
                    return replacement

    lowered_text = _prepare_slide_text(text_content, limit=160).lower()
    if "output volume size" in lowered_text or "output size" in lowered_text:
        return "卷积层例题"
    if "number of parameters" in lowered_text:
        return "卷积层例题"
    if "pad with 1 pixel border" in lowered_text or "zero pad" in lowered_text:
        return "零填充与尺寸保持"
    if "receptive field" in lowered_text:
        return "从神经元视角理解卷积"
    if "max pool" in lowered_text:
        return "最大池化"
    if "average pool" in lowered_text:
        return "平均池化"
    if "pooling" in lowered_text:
        return "池化层"
    if "convolution" in lowered_text or "filter" in lowered_text:
        return "卷积层"

    normalized_title = _humanize_label(title or "")
    return "" if _is_noise_term(normalized_title) else normalized_title


def _extract_chinese_fact(text_content: str) -> str:
    prepared = _prepare_slide_text(text_content, limit=140)
    if not prepared:
        return ""
    if _is_mostly_english(prepared) or _is_formula_heavy(prepared):
        return ""
    if not _contains_enough_chinese(prepared):
        return ""
    return _truncate_sentence(prepared, 88)


def _is_noise_term(text: str) -> bool:
    if not text:
        return True
    if len(text) <= 1:
        return True
    if re.fullmatch(r"[\d\s./xX+\-=()?:!]+", text):
        return True
    return False


def _needs_teacher_style_rewrite(text: str) -> bool:
    if not text:
        return True
    if not _contains_enough_chinese(text):
        return True
    if len(text) < 18:
        return True
    if _is_mostly_english(text):
        return True
    if _contains_forbidden_phrase(text):
        return True
    return False


def _looks_like_slide_reading(script: str, text_content: str) -> bool:
    normalized_script = _translate_common_terms(_clean_text(script)).lower()
    normalized_slide = _prepare_slide_text(text_content, limit=320).lower()
    if not normalized_script or not normalized_slide:
        return False

    if normalized_script == normalized_slide:
        return True
    if normalized_script in normalized_slide and len(normalized_script) >= 18:
        return True

    script_chinese_count = len(re.findall(r"[\u4e00-\u9fff]", normalized_script))
    slide_english_terms = {term for term in re.findall(r"[a-z]{3,}", normalized_slide)}
    script_english_terms = {term for term in re.findall(r"[a-z]{3,}", normalized_script)}
    overlap = len(slide_english_terms & script_english_terms)

    if overlap >= 4 and script_chinese_count < 24:
        return True
    if _is_formula_heavy(normalized_script) and script_chinese_count < 20:
        return True
    if len(normalized_script) < 42 and _is_formula_heavy(normalized_slide):
        return True
    return False


def _smooth_teacher_tone(text: str) -> str:
    normalized = _clean_text(text)
    replacements = {
        "这里是在说明": "这里要理解",
        "这里是在总结": "这里可以总结",
        "这里是在回收": "这里是在梳理",
        "这一部分先把": "这部分先把",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _contains_enough_chinese(text: str) -> bool:
    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    alpha_count = len(re.findall(r"[A-Za-z]", text))
    return chinese_count > 0 and chinese_count * 2 >= max(alpha_count, 1)


def _is_mostly_english(text: str) -> bool:
    normalized = _clean_text(text)
    if not normalized:
        return False
    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", normalized))
    alpha_count = len(re.findall(r"[A-Za-z]", normalized))
    return alpha_count > max(chinese_count * 2, 18)


def _is_formula_heavy(text: str) -> bool:
    normalized = _clean_text(text)
    if not normalized:
        return False
    digit_count = len(re.findall(r"\d", normalized))
    symbol_count = len(re.findall(r"[=+\-*/xX()]", normalized))
    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", normalized))
    return digit_count + symbol_count > max(chinese_count * 2, 12)
