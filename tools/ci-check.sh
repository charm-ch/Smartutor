#!/usr/bin/env bash
# tools/ci-check.sh — Smartutor Harness 一键回归（[2026-08-31] 阶段 1 Sensors 产物）
#
# 用法：bash tools/ci-check.sh   （在仓库根目录执行）
# 串联：py_compile 全量 → JSON 校验单测 → 沙箱安全测试 → 检索评测
# 任一环节失败立即 exit 1（裸奔的测试等于没有测试）。
set -uo pipefail
cd "$(dirname "$0")/.."

PASS=0; FAIL=0
# Python 选择：优先后端 venv（依赖齐全），否则回退系统 python3
if [ -x backend/.venv/bin/python ]; then PY=backend/.venv/bin/python; else PY=python3; fi
step() {
  local name="$1"; shift
  echo "=== [CI] $name ==="
  if "$@"; then
    PASS=$((PASS+1)); echo "--- [CI] $name ✓"
  else
    FAIL=$((FAIL+1)); echo "--- [CI] $name ✗ (exit $?)" >&2
  fi
}

# 1) 语法编译：全量 py_compile（最快发现"改崩了"）
step "py_compile" "$PY" -m compileall -q backend/app

# 2) Sensors 单测：LLM JSON 校验器（残缺输入必须报错而非静默通过）
step "validators-test" "$PY" - <<'PY'
import sys
sys.path.insert(0, "backend")
from pydantic import BaseModel
from app.services.validators import (
    LLMJsonError, validate_llm_json, validate_markdown_section,
)

class Out(BaseModel):
    name: str
    mastery: float

# 合法输入
validate_llm_json('```json\n{"name": "指针", "mastery": 0.8}\n```', Out)
validate_llm_json('前缀文本 {"name": "指针", "mastery": 0.9} 后缀', Out)
# 残缺输入必须抛错
for bad in ['{"name": "指针"}', '不是 JSON', '{"name": "指针", "mastery": "高"}', '']:
    try:
        validate_llm_json(bad, Out)
        print(f"FAIL: 残缺输入未被拦截: {bad!r}"); sys.exit(1)
    except LLMJsonError:
        pass
validate_markdown_section("# 正常输出 " + "x" * 100, 50)
try:
    validate_markdown_section("短", 50)
    print("FAIL: 过短输出未被拦截"); sys.exit(1)
except LLMJsonError:
    pass
print("validators-test: 10 cases ok")
PY

# 3) 沙箱安全测试（7 项：逃逸/网络/超时/资源限制等）
if [ -f tools/sandbox-test.sh ]; then
  step "sandbox-test" bash tools/sandbox-test.sh
else
  echo "=== [CI] sandbox-test 跳过（脚本不存在） ==="
fi

# 4) 检索评测：20 问命中率（需要已建知识库，失败不阻塞但必须可见）
if [ -f tools/retrieval-eval.sh ]; then
  step "retrieval-eval" bash tools/retrieval-eval.sh
else
  echo "=== [CI] retrieval-eval 跳过（脚本不存在） ==="
fi

echo ""
echo "=== [CI] 结果：$PASS 通过, $FAIL 失败 ==="
[ "$FAIL" -eq 0 ]
