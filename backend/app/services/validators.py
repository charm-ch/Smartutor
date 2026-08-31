"""Sensors 传感层：LLM JSON 输出的确定性校验。

原则（Harness·Sensors）：能用确定性规则判断的，绝不让 LLM 自己给自己发奖状。
LLM 返回的 JSON 必须通过 Pydantic Schema 校验；校验失败由调用方带错误信息
重试 1 次；再失败抛 LLMJsonError（E_VALIDATE_FAILED），禁止静默回退空结构。

[2026-08-31] 源自事故：user_profile 正则抽 JSON 失败时静默回退 {}，
用户拿到空画像却无任何报错。
"""
import json
import re

from pydantic import BaseModel, ValidationError


class LLMJsonError(Exception):
    """LLM 输出未通过 JSON/Schema 校验（映射契约错误码 E_VALIDATE_FAILED）。"""


def extract_json(text: str) -> str | None:
    """从 LLM 输出中提取 JSON：优先 ```json 围栏，其次首个 { ... } 平衡块。"""
    m = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if m:
        return m.group(1)
    m = re.search(r"\{[\s\S]*\}", text)
    return m.group(0) if m else None


def validate_llm_json(raw: str, schema: type[BaseModel]) -> BaseModel:
    """提取并按 Schema 校验 LLM 输出。失败抛 LLMJsonError（含错误摘要，供重试提示）。"""
    json_str = extract_json(raw)
    if not json_str:
        raise LLMJsonError("E_VALIDATE_FAILED: 输出中未找到 JSON")
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise LLMJsonError(f"E_VALIDATE_FAILED: JSON 解析失败：{e}") from None
    try:
        return schema.model_validate(data)
    except ValidationError as e:
        summary = "; ".join(
            f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:5]
        )
        raise LLMJsonError(f"E_VALIDATE_FAILED: Schema 校验失败：{summary}") from None


def validate_markdown_section(text: str, min_length: int = 100) -> None:
    """校验 Markdown 生成类输出非空且达到最小长度（模拟卷等非 JSON 输出的传感器）。"""
    if not text or len(text.strip()) < min_length:
        raise LLMJsonError(
            f"E_VALIDATE_FAILED: 生成内容过短（{len(text.strip())} 字符 < {min_length}），疑似生成失败"
        )
