"""Permissions 权限层：写操作 Bearer Token 校验。

原则（Harness·Permissions）：模型不是安全边界，Harness 才是。
- settings.api_token 为空 = 未启用（本地调试模式，全部放行）
- 启用后：写操作（POST/PUT/PATCH/DELETE）必须携带 Authorization: Bearer <token>
- 读操作（GET/HEAD/OPTIONS）始终放行

[2026-08-31] 源自审计结论：此前全部 API 无认证，任何人可删知识库/传文件。
"""
from fastapi import HTTPException, Request

from app.core.config import settings

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def require_token(request: Request) -> None:
    """FastAPI dependency：挂到路由上统一校验。"""
    if not settings.api_token:
        return  # 未启用认证
    if request.method not in _WRITE_METHODS:
        return  # 读操作放行
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {settings.api_token}":
        raise HTTPException(
            status_code=401,
            detail={"code": "E_UNAUTHORIZED", "message": "缺少或无效的 API Token"},
        )
