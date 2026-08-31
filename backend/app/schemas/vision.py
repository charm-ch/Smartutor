"""VISION 组：视觉识别的数据模型（契约 §4）。"""
from pydantic import BaseModel


class VisionRequest(BaseModel):
    image_url: str


class VisionResponse(BaseModel):
    text: str
    code: str | None = None
    error: str | None = None
