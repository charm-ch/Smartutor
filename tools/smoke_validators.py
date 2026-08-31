"""validators 本地冒烟测试（对应 ci-check.sh 第 2 步）。"""
import sys

sys.path.insert(0, "backend")

from pydantic import BaseModel  # noqa: E402

from app.services.validators import (  # noqa: E402
    LLMJsonError,
    validate_llm_json,
    validate_markdown_section,
)


class Out(BaseModel):
    name: str
    mastery: float


cases_ok = [
    '```json\n{"name": "指针", "mastery": 0.8}\n```',
    '前缀文本 {"name": "指针", "mastery": 0.9} 后缀',
]
cases_bad = [
    '{"name": "指针"}',                      # 缺 mastery
    '不是 JSON',                              # 无 JSON
    '{"name": "指针", "mastery": "高"}',      # 类型错误
    '',                                       # 空输出
]

for c in cases_ok:
    validate_llm_json(c, Out)

for c in cases_bad:
    try:
        validate_llm_json(c, Out)
        print(f"FAIL: 残缺输入未被拦截: {c!r}")
        sys.exit(1)
    except LLMJsonError:
        pass

validate_markdown_section("# 正常输出 " + "x" * 100, 50)
try:
    validate_markdown_section("短", 50)
    print("FAIL: 过短输出未被拦截")
    sys.exit(1)
except LLMJsonError:
    pass

print(f"validators smoke: {len(cases_ok)} ok + {len(cases_bad)} bad 全部符合预期")
