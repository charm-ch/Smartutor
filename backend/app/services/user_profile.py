"""个性化学习画像服务（M7）：分析用户学习情况，生成强弱点分析和建议。

[2026-08-31] Harness 加固：
- Sensors：JSON 输出走 Pydantic Schema 校验，失败带错误重试 1 次，禁止静默回退 {}
- Memory：task_state 检查点，每阶段落库，进程重启后可查进度（>7 天自动清理）
- 增量画像：与该会话上次画像按知识点 merge，输出掌握度对比
"""
import json
import uuid

from app.core import db
from app.schemas.user_profile import UserProfileResponse
from app.services import llm, validators


class UserProfileError(Exception):
    """用户画像生成失败。stage/suggestion 用于结构化错误上报（Harness·Loop）。"""

    def __init__(self, message: str, stage: str = "", suggestion: str = ""):
        super().__init__(message)
        self.stage = stage
        self.suggestion = suggestion


def _new_task_id() -> str:
    return f"task_{uuid.uuid4().hex[:12]}"


async def _checkpoint(task_id: str, ref_id: str, status: str, stage: str, payload: dict) -> None:
    """Memory 检查点：每完成一个阶段落一次库；顺带清理 7 天前过期任务。"""
    await db.execute(
        """INSERT INTO task_state (task_id, kind, ref_id, status, stage, payload, updated_at)
           VALUES (%s, 'user_profile', %s, %s, %s, %s, now())
           ON CONFLICT (task_id) DO UPDATE
           SET status=EXCLUDED.status, stage=EXCLUDED.stage,
               payload=EXCLUDED.payload, updated_at=now()""",
        (task_id, ref_id, status, stage, db.dumps(payload)),
    )
    await db.execute("DELETE FROM task_state WHERE updated_at < now() - interval '7 days'")


async def generate_user_profile(conversation_id: str) -> dict:
    """基于用户对话历史生成个性化学习画像。
    
    Args:
        conversation_id: 会话ID
    
    Returns:
        UserProfileResponse 结构 + task_id / parse_status / comparison（历史对比）
    """
    task_id = _new_task_id()

    # 1. 获取用户对话历史（stage: fetch_history）
    messages = await db.fetch_all(
        """SELECT role, content, citations, run 
           FROM messages 
           WHERE conversation_id=%s 
           ORDER BY created_at""",
        (conversation_id,)
    )
    
    if not messages:
        raise UserProfileError("该会话暂无对话记录", stage="fetch_history")
    
    # 2. 提取用户提问
    user_questions = [m["content"] for m in messages if m["role"] == "user"]
    assistant_answers = [m["content"] for m in messages if m["role"] == "assistant"]
    
    if not user_questions:
        raise UserProfileError("该会话暂无用户提问", stage="fetch_history")

    await _checkpoint(task_id, conversation_id, "running", "fetch_history",
                      {"total_messages": len(messages)})
    
    # 3. 分析知识点掌握情况
    analysis_prompt = f"""请分析以下学生的学习对话记录，评估其知识点掌握情况：

【学生提问记录】（共{len(user_questions)}个问题）
{chr(10).join(f"{i+1}. {q[:200]}" for i, q in enumerate(user_questions[:15]))}

【助教回答记录】（共{len(assistant_answers)}个回答）
{chr(10).join(f"{i+1}. {a[:300]}" for i, a in enumerate(assistant_answers[:10]))}

请从以下维度分析：

1. **知识点覆盖**：列出学生涉及的所有知识点（如：指针、数组、函数、内存管理等）

2. **掌握程度评估**（0-1分，1为完全掌握）：
   - 对每个知识点给出掌握度评分
   - 评分依据：提问频率、问题深度、是否重复提问同类问题

3. **薄弱环节**：
   - 频繁提问的知识点
   - 理解有误的知识点
   - 需要加强的知识点

4. **优势领域**：
   - 掌握较好的知识点
   - 能够灵活应用的知识点

5. **个性化学习建议**：
   - 针对薄弱环节的具体建议
   - 推荐的学习资源或练习方向
   - 学习方法和策略建议

请用 JSON 格式输出，结构如下：
```json
{{
  "knowledge_points": [
    {{"name": "知识点名称", "mastery": 0.8, "frequency": 5}}
  ],
  "weak_points": ["薄弱知识点 1", "薄弱知识点 2"],
  "strong_points": ["优势知识点 1", "优势知识点 2"],
  "suggestions": ["建议 1", "建议 2", "建议 3"],
  "statistics": {{
    "total_questions": 10,
    "topics_covered": 5,
    "learning_style": "理论型/实践型/综合型"
  }}
}}
```

注意：
- 掌握度评分要客观准确
- 建议要具体可操作
- 语气要鼓励性，避免打击学生信心"""
    
    # 4. 调用LLM生成画像（Sensors：Schema 校验 + 带错误重试 1 次）
    parse_status = "ok"
    profile: UserProfileResponse | None = None
    last_err = ""
    for attempt in range(2):
        prompt = analysis_prompt
        if attempt == 1:
            prompt += (
                f"\n\n【重要】你上一次的输出未通过校验：{last_err}\n"
                "请严格按上述 JSON 结构重新输出，确保是合法 JSON 且 mastery 为 0-1 的数字。"
            )
        profile_result = await llm.chat_once([{"role": "user", "content": prompt}])
        profile_content = profile_result.get("content", "")
        try:
            profile = validators.validate_llm_json(profile_content, UserProfileResponse)
            parse_status = "ok" if attempt == 0 else "retried_ok"
            break
        except validators.LLMJsonError as e:
            last_err = str(e)
    if profile is None:
        await _checkpoint(task_id, conversation_id, "failed", "analyze", {"error": last_err})
        raise UserProfileError(
            f"画像 JSON 校验失败：{last_err}",
            stage="analyze",
            suggestion="请重试一次；若持续失败，请检查会话记录是否过短或模型输出是否异常",
        )

    await _checkpoint(task_id, conversation_id, "running", "analyze",
                      {"knowledge_points": len(profile.knowledge_points)})

    # 5. 增量对比：取该会话上一次成功画像，按知识点名 merge（Memory 层）
    comparison: list[dict] = []
    prev = await db.fetch_one(
        """SELECT payload FROM task_state
           WHERE kind='user_profile' AND ref_id=%s AND status='done' AND task_id <> %s
           ORDER BY updated_at DESC LIMIT 1""",
        (conversation_id, task_id),
    )
    if prev:
        prev_kp = {p.get("name"): p.get("mastery")
                   for p in (prev["payload"] or {}).get("knowledge_points", [])}
        for kp in profile.knowledge_points:
            if kp.name in prev_kp:
                comparison.append({
                    "name": kp.name,
                    "previous_mastery": prev_kp[kp.name],
                    "current_mastery": kp.mastery,
                })

    # 6. 检查点收尾 + 组装响应
    result = profile.model_dump()
    await _checkpoint(task_id, conversation_id, "done", "done", result)
    result["task_id"] = task_id
    result["parse_status"] = parse_status
    result["comparison"] = comparison
    return result
