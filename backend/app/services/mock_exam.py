"""模拟试卷生成服务（M6）：基于历年真题生成风格类似的模拟试题。

[2026-08-31] Harness 加固：
- Sensors：各阶段生成结果走 validate_markdown_section 非空校验（LLM 返回空内容直接报错）
- Memory：task_state 检查点，每阶段（style_analysis/question_gen/answers）落库
- Loop：异常带 stage/suggestion，错误响应为 {stage, detail, suggestion} 三元组
"""
import uuid

from app.core import db
from app.services import llm, validators


class MockExamError(Exception):
    """模拟试卷生成失败。stage/suggestion 用于结构化错误上报（Harness·Loop）。"""

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
           VALUES (%s, 'mock_exam', %s, %s, %s, %s, now())
           ON CONFLICT (task_id) DO UPDATE
           SET status=EXCLUDED.status, stage=EXCLUDED.stage,
               payload=EXCLUDED.payload, updated_at=now()""",
        (task_id, ref_id, status, stage, db.dumps(payload)),
    )
    await db.execute("DELETE FROM task_state WHERE updated_at < now() - interval '7 days'")


async def generate_mock_exam(
    kb_id: str,
    num_questions: int = 10,
    difficulty: str = "medium",
    include_answers: bool = True,
) -> dict:
    """基于知识库中的历年真题生成模拟试题。
    
    Args:
        kb_id: 知识库ID（包含历年真题）
        num_questions: 题目数量
        difficulty: 难度（easy/medium/hard）
        include_answers: 是否包含参考答案
    
    Returns:
        {exam, answers, analysis} + task_id / parse_status
    """
    # 1. 检索知识库中的历年真题
    from app.services import rag

    task_id = _new_task_id()
    retrieved = await rag.retrieve(kb_id, "历年真题 模拟试题", top_k=10)

    if not retrieved:
        raise MockExamError(
            "知识库中未找到相关题目，请先上传历年真题PDF",
            stage="retrieve",
            suggestion="请确认该知识库已上传真题 PDF 且解析状态为 parsed",
        )

    await _checkpoint(task_id, kb_id, "running", "retrieve", {"chunks": len(retrieved)})
    
    # 2. 组装题目风格分析提示词
    style_analysis_prompt = f"""请分析以下历年真题的题目风格（题型、知识点分布、难度特点）：

{chr(10).join(f"[{i+1}] {r.get('content', r['snippet'])[:500]}" for i, r in enumerate(retrieved[:5]))}

请从以下维度分析：
1. 题型分布（选择题/填空题/计算题/证明题等）
2. 知识点覆盖（哪些章节/主题出现频率高）
3. 难度特点（计算量、思维深度、技巧性）
4. 命题风格（直接考察/综合应用/创新题型）

请用简洁的要点形式输出分析结果。"""
    
    # 3. 调用LLM分析题目风格（Sensors：输出非空校验）
    style_analysis = await llm.chat_once([
        {"role": "user", "content": style_analysis_prompt}
    ])
    style_text = style_analysis.get("content", "")
    try:
        validators.validate_markdown_section(style_text, min_length=50)
    except validators.LLMJsonError as e:
        await _checkpoint(task_id, kb_id, "failed", "style_analysis", {"error": str(e)})
        raise MockExamError(
            str(e), stage="style_analysis",
            suggestion="风格分析输出异常，请重试一次；若持续失败请检查模型服务状态",
        ) from None

    await _checkpoint(task_id, kb_id, "running", "style_analysis", {"length": len(style_text)})
    
    # 4. 生成模拟试题
    difficulty_desc = {
        "easy": "基础题为主，侧重概念理解和基本计算",
        "medium": "中等难度，基础题与综合题各半",
        "hard": "较高难度，侧重综合应用和创新思维"
    }.get(difficulty, "中等难度")
    
    exam_prompt = f"""基于以下历年真题风格分析，生成一份包含{num_questions}道题的模拟试题：

【题目风格分析】
{style_text}

【难度要求】
{difficulty_desc}

【输出格式】
请按以下格式输出：

# 模拟试题

## 一、选择题（每题X分）
1. [题目内容]
   A. [选项A]
   B. [选项B]
   C. [选项C]
   D. [选项D]

## 二、填空题（每题X分）
1. [题目内容]

## 三、计算题（每题X分）
1. [题目内容]

## 四、证明题（每题X分）
1. [题目内容]

注意：
- 题目风格应与历年真题保持一致
- 知识点覆盖要全面
- 难度梯度要合理
- 不要直接复制真题，要生成新题目"""
    
    exam_result = await llm.chat_once([
        {"role": "user", "content": exam_prompt}
    ])
    exam_content = exam_result.get("content", "")
    try:
        validators.validate_markdown_section(exam_content, min_length=200)
    except validators.LLMJsonError as e:
        await _checkpoint(task_id, kb_id, "failed", "question_gen", {"error": str(e)})
        raise MockExamError(
            str(e), stage="question_gen",
            suggestion="出题阶段输出过短或为空，请重试；可尝试降低题目数量",
        ) from None

    await _checkpoint(task_id, kb_id, "running", "question_gen", {"length": len(exam_content)})
    
    # 5. 生成参考答案
    answers_content = ""
    if include_answers:
        answers_prompt = f"""请为以下模拟试题生成详细的参考答案：

{exam_content}

【输出格式】
# 参考答案

## 一、选择题
1. [答案] [简要解析]

## 二、填空题
1. [答案] [简要解析]

## 三、计算题
1. [详细解答过程]

## 四、证明题
1. [完整证明过程]

注意：
- 解答过程要详细清晰
- 关键步骤要标注说明
- 证明题要逻辑严密"""
        
        answers_result = await llm.chat_once([
            {"role": "user", "content": answers_prompt}
        ])
        answers_content = answers_result.get("content", "")
        try:
            validators.validate_markdown_section(answers_content, min_length=100)
        except validators.LLMJsonError as e:
            await _checkpoint(task_id, kb_id, "failed", "answers", {"error": str(e)})
            raise MockExamError(
                str(e), stage="answers",
                suggestion="答案生成异常，请重试；试题本身已生成，可关闭“包含答案”后重试",
            ) from None

    result = {"exam": exam_content, "answers": answers_content, "analysis": style_text}
    await _checkpoint(task_id, kb_id, "done", "done", {"exam_length": len(exam_content)})
    result["task_id"] = task_id
    return result
