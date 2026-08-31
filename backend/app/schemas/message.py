"""MSG 组：会话与答疑的数据模型（契约 §2）。"""
from datetime import datetime

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    type: str = "image"
    url: str


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
    attachments: list[Attachment] = Field(default_factory=list)


class Citation(BaseModel):
    """溯源条目：回答中 [n] 标记与 citations 一一对应。"""

    index: int
    doc_name: str
    chapter: str = ""
    page: int = 0
    snippet: str = ""
    verified: bool = True


class RunResult(BaseModel):
    """沙箱运行结果（仅本轮触发沙箱时非空）。"""

    code: str = ""
    output: str = ""
    exit_code: int | None = None
    time_ms: int = 0


class MessageOut(BaseModel):
    id: str
    role: str  # user | assistant
    content: str
    attachments: list[Attachment] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    run: RunResult | None = None
    created_at: datetime


class ConversationOut(BaseModel):
    conversation_id: str


class MessageListOut(BaseModel):
    messages: list[MessageOut]
