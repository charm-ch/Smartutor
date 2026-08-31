"""MSG 组路由（M2）：会话与答疑，契约 §2。SSE 流式核心链路。

编排流程（契约 §2.2 事件顺序 token → (run)? → citation → done）：
  1. 保存用户消息
  2. 附件含 image → M4 视觉识别，提取 code/error 注入上下文
  3. 检测到代码 → M3 沙箱运行（run 事件）
  4. M1 检索 Top-k（四元组）→ 组装提示词
  5. 流式生成（token 事件），强制内嵌 [n] 引用
  6. 溯源一致性校验：[n] 必须存在于检索结果，否则 verified=false
  7. citation + done 事件；持久化 assistant 消息
"""
import json
import re
import uuid

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.core import db
from app.schemas.message import (
    Attachment,
    Citation,
    ConversationOut,
    MessageCreate,
    MessageListOut,
    MessageOut,
    RunResult,
)
from app.services import llm, rag, sandbox, vision

router = APIRouter()

_HISTORY_TURNS = 8  # 参与上下文的历史消息数

_CODE_BLOCK_RE = re.compile(r"```(?:c|cpp|c\+\+|python|py)?\s*\n([\s\S]*?)```", re.I)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _detect_code(text: str) -> tuple[str, str] | None:
    """从用户输入中提取待运行代码：优先 ``` 代码块，其次特征启发。返回 (language, code)。"""
    for m in _CODE_BLOCK_RE.finditer(text):
        code = m.group(1).strip()
        if len(code) < 8:
            continue
        lang = _guess_lang(code, m.group(1)[:16])
        if lang:
            return lang, code
    # 无围栏代码块时的特征检测：从特征标记处截取代码
    for marker in ("#include", "int main"):
        pos = text.find(marker)
        if pos >= 0:
            return "c", text[pos:].strip()
    if re.search(r"^\s*(def |import |from .+ import|print\()", text, re.M) and len(text) > 40 and "=" in text:
        return "python", text.strip()
    return None


def _guess_lang(code: str, fence: str) -> str | None:
    fence = fence.lower()
    if "c" in fence or "cpp" in fence or "+" in fence:
        return "c"
    if "py" in fence:
        return "python"
    if "#include" in code or re.search(r"\bint\s+main\s*\(", code):
        return "c"
    if re.search(r"^\s*(def |import |from .+ import|print\()", code, re.M):
        return "python"
    return None


_SYSTEM_PROMPT = (
    "你是「智学」课程助教，为大学生辅导编程课程（C 语言/Python 等）。遵守：\n"
    "1. 优先依据提供的【课程资料】回答，引用资料时必须标注编号，如 [1]、[2]。\n"
    "2. 资料不足以回答时，可结合自身知识回答，但禁止编造不存在的引用编号。\n"
    "3. 学生提供了代码或报错时：先指出问题根因，再给出完整可运行的修复代码（用 ``` 代码块）。\n"
    "4. 回答简洁、结构清晰，使用中文。\n"
    "5. **知识库外问题处理**：如果学生的问题明显超出课程资料范围（如问数学题、历史事件、其他编程语言等），\n"
    "   应礼貌说明本课程资料未覆盖该主题，建议学生查阅相关课程或教材，但仍可提供简要指导。\n"
    "6. **格式要求**：使用 Markdown 格式组织回答，小标题用 `###` 加粗，关键结论用 `**加粗**` 突出，\n"
    "   代码用 ``` 语言块包裹，列表用 `-` 或 `1.` 格式。"
)


def _build_context(question: str, retrieved: list, run: RunResult | None) -> str:
    parts: list[str] = []
    if retrieved:
        refs = "\n\n".join(
            f"[{i + 1}] 《{r['doc_name']}》{r['chapter']} 第{r['page']}页：\n{r.get('content') or r['snippet']}"
            for i, r in enumerate(retrieved)
        )
        parts.append("【课程资料】\n" + refs)
    else:
        # 无检索结果时，提示 LLM 这是知识库外问题
        parts.append("【提示】未检索到相关课程资料，请根据自身知识回答，并说明本课程资料未覆盖该主题。")
    if run is not None:
        parts.append(
            f"【代码沙箱运行结果】exit_code={run.exit_code}，耗时 {run.time_ms}ms\n"
            f"输出/报错：\n{run.output or '(空)'}"
        )
    parts.append(f"【学生的问题】\n{question}")
    return "\n\n".join(parts)


def _verify_citations(answer: str, retrieved: list) -> list[Citation]:
    """溯源一致性校验：回答中的 [n] 对照检索结果。"""
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer)})
    citations: list[Citation] = []
    for n in cited:
        if 1 <= n <= len(retrieved):
            r = retrieved[n - 1]
            citations.append(
                Citation(
                    index=n,
                    doc_name=r["doc_name"],
                    chapter=r["chapter"],
                    page=r["page"],
                    snippet=r["snippet"],
                    verified=True,
                )
            )
        else:
            citations.append(
                Citation(
                    index=n,
                    doc_name="（未核实引用）",
                    chapter="",
                    page=0,
                    snippet="该引用编号未命中本次课程资料检索结果，内容请人工复核。",
                    verified=False,
                )
            )
    return citations


@router.post("", response_model=ConversationOut)
async def create_conversation(payload: dict) -> ConversationOut:
    kb_id = (payload or {}).get("kb_id", "")
    if kb_id and await db.fetch_one("SELECT id FROM kb WHERE id=%s", (kb_id,)) is None:
        raise HTTPException(status_code=404, detail={"code": "E_NOT_FOUND", "message": "知识库不存在"})
    conv_id = _new_id("conv")
    await db.execute(
        "INSERT INTO conversations (id, kb_id, title) VALUES (%s, %s, %s)",
        (conv_id, kb_id or None, "新对话"),
    )
    return ConversationOut(conversation_id=conv_id)


@router.post("/{cid}/messages")
async def send_message(cid: str, payload: MessageCreate) -> EventSourceResponse:
    conv = await db.fetch_one("SELECT id, kb_id FROM conversations WHERE id=%s", (cid,))
    if conv is None:
        raise HTTPException(status_code=404, detail={"code": "E_NOT_FOUND", "message": "会话不存在"})

    question = payload.content

    async def event_gen():
        user_msg_id = _new_id("msg")
        vision_text = ""
        run_result: RunResult | None = None
        retrieved: list = []
        answer_text = ""
        citations: list[Citation] = []

        try:
            # 0) 视觉附件（如有）→ 识别结果并入问题
            for att in payload.attachments:
                if att.type == "image":
                    try:
                        vr = await vision.analyze(att.url)
                        vision_text += (vr.code or "") + "\n" + (vr.error or "")
                    except vision.VisionError as e:
                        vision_text += f"\n（图片识别失败：{e}）"

            question_full = question + ("\n【截图识别内容】\n" + vision_text if vision_text.strip() else "")

            # 1) 持久化用户消息
            await db.execute(
                """INSERT INTO messages (id, conversation_id, role, content, attachments)
                   VALUES (%s, %s, 'user', %s, %s)""",
                (user_msg_id, cid, question_full,
                 db.dumps([a.model_dump() for a in payload.attachments])),
            )

            # 2) 代码检测 → 沙箱运行（run 事件）
            detected = _detect_code(question_full)
            if detected:
                lang, code = detected
                try:
                    outcome = await sandbox.execute(lang, code)
                    output = outcome.stdout or ""
                    if outcome.stderr:
                        output += ("\n[stderr]\n" if output else "") + outcome.stderr
                    run_result = RunResult(
                        code=code,
                        output=output[:4000],
                        exit_code=outcome.exit_code,
                        time_ms=outcome.time_ms,
                    )
                except sandbox.SandboxError as e:
                    code_str = str(e)
                    if code_str == "E_TIMEOUT":
                        yield {"event": "run", "data": json.dumps(
                            {"code": code, "output": "运行超时（10s），可能存在死循环", "exit_code": None, "time_ms": 10000},
                            ensure_ascii=False)}
                    else:
                        yield {"event": "run", "data": json.dumps(
                            {"code": code, "output": f"沙箱错误: {code_str}", "exit_code": None, "time_ms": 0},
                            ensure_ascii=False)}
                else:
                    yield {"event": "run", "data": json.dumps(run_result.model_dump(), ensure_ascii=False)}

            # 3) 检索（无 KB 或检索失败时降级为空）
            if conv["kb_id"]:
                try:
                    retrieved = [dict(r) for r in await rag.retrieve(conv["kb_id"], question)]
                except rag.RAGError:
                    retrieved = []

            # 4) 流式生成
            history_rows = await db.fetch_all(
                """SELECT role, content FROM messages
                   WHERE conversation_id=%s AND role='assistant'
                   ORDER BY created_at DESC LIMIT %s""",
                (cid, _HISTORY_TURNS),
            )
            messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
            for h in reversed(history_rows):
                messages.append({"role": "assistant", "content": h["content"][:2000]})
            messages.append({"role": "user", "content": _build_context(question_full, retrieved, run_result)})

            async for token in llm.chat_stream(messages):
                answer_text += token
                yield {"event": "token", "data": json.dumps({"text": token}, ensure_ascii=False)}

            # 5) 溯源一致性校验
            citations = _verify_citations(answer_text, retrieved)
            yield {"event": "citation", "data": json.dumps(
                {"citations": [c.model_dump() for c in citations]}, ensure_ascii=False)}

            # 6) 持久化 + done
            msg_id = _new_id("msg")
            await db.execute(
                """INSERT INTO messages (id, conversation_id, role, content, citations, run)
                   VALUES (%s, %s, 'assistant', %s, %s, %s)""",
                (msg_id, cid, answer_text,
                 db.dumps([c.model_dump() for c in citations]),
                 db.dumps(run_result.model_dump()) if run_result else None),
            )
            if len(question) > 40:
                await db.execute("UPDATE conversations SET title=%s WHERE id=%s", (question[:40], cid))
            yield {"event": "done", "data": json.dumps({"message_id": msg_id}, ensure_ascii=False)}

        except Exception as e:  # noqa: BLE001
            yield {"event": "error", "data": json.dumps(
                {"code": "E_INTERNAL", "message": str(e)[:200]}, ensure_ascii=False)}

    return EventSourceResponse(event_gen())


@router.get("/{cid}/messages", response_model=MessageListOut)
async def list_messages(cid: str) -> MessageListOut:
    rows = await db.fetch_all(
        """SELECT id, role, content, attachments, citations, run, created_at
           FROM messages WHERE conversation_id=%s ORDER BY created_at""",
        (cid,),
    )
    messages = []
    for r in rows:
        messages.append(
            MessageOut(
                id=r["id"],
                role=r["role"],
                content=r["content"],
                attachments=[Attachment(**a) for a in (r["attachments"] or [])],
                citations=[Citation(**c) for c in (r["citations"] or [])],
                run=RunResult(**r["run"]) if r["run"] else None,
                created_at=r["created_at"],
            )
        )
    return MessageListOut(messages=messages)
