"""设置组：运行时 API 配置的数据模型。

遵循 USTC LLM 平台文档建议：API Key 保存在服务端，不写入前端页面。
GET 只返回脱敏值（sk-****后4位）。
"""
from pydantic import BaseModel, Field


class SettingsPayload(BaseModel):
    """保存配置。api_key 为空字符串表示不更新（保留旧值）。"""

    base_url: str = Field(default="https://api.llm.ustc.edu.cn/v1")
    api_key: str = Field(default="", max_length=200)
    chat_model: str = Field(default="deepseek-v4-flash", max_length=100)
    vision_model: str = Field(default="", max_length=100)
    embedding_model: str = Field(default="BAAI/bge-small-zh-v1.5", max_length=100)
    embedding_use_local: bool = True


class SettingsOut(BaseModel):
    """前端可见配置（脱敏）。"""

    base_url: str
    chat_model: str
    vision_model: str
    embedding_model: str
    embedding_use_local: bool
    api_key_masked: str = ""  # sk-****abcd；未配置时为空
    has_api_key: bool = False


class TestRequest(BaseModel):
    """测试连接：允许临时覆盖配置（不保存）。"""

    base_url: str = "https://api.llm.ustc.edu.cn/v1"
    api_key: str = Field(min_length=1, max_length=200)


class TestResponse(BaseModel):
    ok: bool
    models: list[str] = []
    message: str = ""
