"""视觉识别服务（M4）：截图 → 结构化提取（code / error）。

识别底座：services.llm.vision_analyze（学校视觉模型），
二次结构化：chat_once 提取 JSON {code, error}。
"""
import json
import re
from dataclasses import dataclass


class VisionError(Exception):
    """视觉识别失败（映射契约错误码 E_VISION）。"""


@dataclass
class VisionResult:
    text: str
    code: str | None = None
    error: str | None = None


def _extract_json(text: str) -> dict | None:
    """从模型输出中容错提取 JSON 对象。"""
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


async def analyze(image_url: str) -> VisionResult:
    """识别报错截图，提取代码与错误信息。"""
    from app.services import llm

    try:
        text = await llm.vision_analyze(
            image_url,
            prompt=(
                "这是一张编程作业/终端报错截图。请完整识别其中的内容，"
                "包括代码与全部报错信息，按原文输出。"
            ),
        )
    except Exception as e:  # noqa: BLE001
        raise VisionError(f"视觉模型调用失败: {e}") from e

    if not text.strip():
        raise VisionError("未能识别出内容")

    # 二次结构化：提取 code / error
    try:
        resp = await llm.chat_once(
            [
                {
                    "role": "user",
                    "content": (
                        "从以下截图识别文本中提取：1) 代码内容(code)；2) 报错信息(error)。"
                        '严格返回 JSON：{"code": "代码或null", "error": "报错或null"}，'
                        "不要输出其他内容。\n\n---\n" + text,
                    ),
                }
            ]
        )
        obj = _extract_json(str(resp.get("content", "")))
        if obj:
            code = obj.get("code")
            error = obj.get("error")
            return VisionResult(
                text=text,
                code=code if isinstance(code, str) and code.strip() and code != "null" else None,
                error=error if isinstance(error, str) and error.strip() and error != "null" else None,
            )
    except Exception:  # noqa: BLE001
        pass  # 结构化失败时仅返回原文

    return VisionResult(text=text)
