"""智学后端入口：挂载全部路由，配置 CORS、数据库连接池生命周期。

[2026-08-31] Harness·Permissions：全局挂 require_token 依赖——
写操作（POST/PUT/PATCH/DELETE）必须携带 Bearer Token（settings.api_token 非空时启用）。
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conversations, execute, kb, mock_exam, runs, settings as settings_api, user_profile, vision
from app.core.auth import require_token
from app.core.config import settings
from app.core.db import close_pool, init_pool


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="智学 · 课程级智能助教 API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"], dependencies=[Depends(require_token)])
app.include_router(kb.router, prefix="/api/kb", tags=["kb"], dependencies=[Depends(require_token)])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"], dependencies=[Depends(require_token)])
app.include_router(execute.router, prefix="/api/execute", tags=["execute"], dependencies=[Depends(require_token)])
app.include_router(vision.router, prefix="/api/vision", tags=["vision"], dependencies=[Depends(require_token)])
app.include_router(mock_exam.router, prefix="/api/mock-exam", tags=["mock-exam"], dependencies=[Depends(require_token)])
app.include_router(user_profile.router, prefix="/api/user-profile", tags=["user-profile"], dependencies=[Depends(require_token)])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
