"""模拟试卷相关的数据模型。"""
from pydantic import BaseModel, Field


class MockExamRequest(BaseModel):
    """生成模拟试卷的请求。"""
    kb_id: str = Field(..., description="知识库ID（包含历年真题）")
    num_questions: int = Field(default=10, ge=1, le=50, description="题目数量")
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$", description="难度")
    include_answers: bool = Field(default=True, description="是否包含参考答案")


class MockExamResponse(BaseModel):
    """模拟试卷响应。"""
    exam: str = Field(..., description="模拟试题内容（Markdown）")
    answers: str = Field(default="", description="参考答案（Markdown）")
    analysis: str = Field(default="", description="题目风格分析")
