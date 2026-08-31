"""个性化学习画像服务（M7）：分析用户学习情况，生成强弱点分析和建议。"""
import asyncio
import json
import re
from collections import Counter

from app.core import db
from app.services import llm


class UserProfileError(Exception):
    """用户画像生成失败。"""


async def generate_user_profile(conversation_id: str) -> dict:
    """基于用户对话历史生成个性化学习画像。
    
    Args:
        conversation_id: 会话ID
    
    Returns:
        {
            "knowledge_points": [{"name": "知识点", "mastery": 0.8, "frequency": 5}],
            "weak_points": ["薄弱知识点列表"],
            "strong_points": ["掌握较好的知识点列表"],
            "suggestions": ["个性化学习建议"],
            "statistics": {
                "total_questions": 10,
                "topics_covered": 5,
                "avg_response_quality": 0.85
            }
        }
    """
    # 1. 获取用户对话历史
    messages = await db.fetch_all(
        """SELECT role, content, citations, run 
           FROM messages 
           WHERE conversation_id=%s 
           ORDER BY created_at""",
        (conversation_id,)
    )
    
    if not messages:
        raise UserProfileError("该会话暂无对话记录")
    
    # 2. 提取用户提问
    user_questions = [m["content"] for m in messages if m["role"] == "user"]
    assistant_answers = [m["content"] for m in messages if m["role"] == "assistant"]
    
    if not user_questions:
        raise UserProfileError("该会话暂无用户提问")
    
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
    
    # 4. 调用LLM生成画像
    profile_result = await llm.chat_once([
        {"role": "user", "content": analysis_prompt}
    ])
    profile_content = profile_result.get("content", "")
    
    # 5. 解析JSON结果
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', profile_content)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 尝试直接解析
        json_match = re.search(r'\{[\s\S]*\}', profile_content)
        json_str = json_match.group(0) if json_match else "{}"
    
    try:
        profile_data = json.loads(json_str)
    except json.JSONDecodeError:
        # 解析失败时返回默认结构
        profile_data = {
            "knowledge_points": [],
            "weak_points": [],
            "strong_points": [],
            "suggestions": ["建议完善对话记录后重新生成画像"],
            "statistics": {
                "total_questions": len(user_questions),
                "topics_covered": 0,
                "learning_style": "未知"
            }
        }
    
    return profile_data
