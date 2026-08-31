"""用户画像相关的数据模型。"""
from pydantic import BaseModel, Field
from typing import List, Optional


class KnowledgePoint(BaseModel):
    """知识点掌握情况。"""
    name: str = Field(..., description="知识点名称")
    mastery: float = Field(..., ge=0, le=1, description="掌握度（0-1）")
    frequency: int = Field(default=0, description="提问频率")


class UserProfileStatistics(BaseModel):
    """学习统计。"""
    total_questions: int = Field(default=0, description="总提问数")
    topics_covered: int = Field(default=0, description="涉及知识点数")
    learning_style: str = Field(default="未知", description="学习风格")


class UserProfileRequest(BaseModel):
    """生成用户画像的请求。"""
    conversation_id: str = Field(..., description="会话ID")


class UserProfileResponse(BaseModel):
    """用户画像响应。"""
    knowledge_points: List[KnowledgePoint] = Field(default_factory=list, description="知识点掌握情况")
    weak_points: List[str] = Field(default_factory=list, description="薄弱环节")
    strong_points: List[str] = Field(default_factory=list, description="优势领域")
    suggestions: List[str] = Field(default_factory=list, description="学习建议")
    statistics: UserProfileStatistics = Field(default_factory=UserProfileStatistics, description="学习统计")
