"""智学后端入口：挂载全部路由，配置 CORS、数据库连接池生命周期。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conversations, execute, kb, mock_exam, settings as settings_api, user_profile, vision
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

app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
app.include_router(kb.router, prefix="/api/kb", tags=["kb"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(execute.router, prefix="/api/execute", tags=["execute"])
app.include_router(vision.router, prefix="/api/vision", tags=["vision"])
app.include_router(mock_exam.router, prefix="/api/mock-exam", tags=["mock-exam"])
app.include_router(user_profile.router, prefix="/api/user-profile", tags=["user-profile"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
