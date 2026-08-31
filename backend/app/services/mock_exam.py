"""模拟试卷生成服务（M6）：基于历年真题生成风格类似的模拟试题。"""
import asyncio
import json
import re
from pathlib import Path

from app.core import db
from app.core.config import settings
from app.services import llm


class MockExamError(Exception):
    """模拟试卷生成失败。"""


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
        {
            "exam": "模拟试题内容（Markdown）",
            "answers": "参考答案（Markdown）",
            "analysis": "题目风格分析"
        }
    """
    # 1. 检索知识库中的历年真题
    from app.services import rag
    
    # 检索所有相关文档
    retrieved = await rag.retrieve(kb_id, "历年真题 模拟试题", top_k=10)
    
    if not retrieved:
        raise MockExamError("知识库中未找到相关题目，请先上传历年真题PDF")
    
    # 2. 组装题目风格分析提示词
    style_analysis_prompt = f"""请分析以下历年真题的题目风格（题型、知识点分布、难度特点）：

{chr(10).join(f"[{i+1}] {r.get('content', r['snippet'])[:500]}" for i, r in enumerate(retrieved[:5]))}

请从以下维度分析：
1. 题型分布（选择题/填空题/计算题/证明题等）
2. 知识点覆盖（哪些章节/主题出现频率高）
3. 难度特点（计算量、思维深度、技巧性）
4. 命题风格（直接考察/综合应用/创新题型）

请用简洁的要点形式输出分析结果。"""
    
    # 3. 调用LLM分析题目风格
    style_analysis = await llm.chat_once([
        {"role": "user", "content": style_analysis_prompt}
    ])
    style_text = style_analysis.get("content", "")
    
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
    
    return {
        "exam": exam_content,
        "answers": answers_content,
        "analysis": style_text
    }
