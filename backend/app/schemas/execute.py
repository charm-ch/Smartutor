"""EXEC 组：代码沙箱的数据模型（契约 §3）。"""
from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    language: str = Field(pattern="^(c|python)$")
    code: str = Field(min_length=1, max_length=20000)
    stdin: str = Field(default="", max_length=10000)


class ExecuteResponse(BaseModel):
    run_id: str
    exit_code: int | None
    stdout: str
    stderr: str
    time_ms: int
