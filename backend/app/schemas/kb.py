"""KB 组：知识库管理的数据模型（契约 §1）。"""
from datetime import datetime

from pydantic import BaseModel, Field


class KBCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class KBDocInfo(BaseModel):
    doc_id: str
    filename: str
    status: str  # parsing | parsed | failed
    chunk_count: int = 0


class KBOut(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: datetime


class KBDocOut(BaseModel):
    doc_id: str
    status: str
    filename: str = ""
    chunk_count: int = 0
    error: str | None = None


class KBDetail(KBOut):
    docs: list[KBDocInfo] = []
    chunk_count: int = 0
