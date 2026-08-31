"""数据库访问层：psycopg3 异步连接池（FastAPI lifespan 中开启/关闭）。

所有 SQL 必须经过本模块，业务代码禁止自行建连。
"""
import json
from contextlib import asynccontextmanager

from psycopg import sql
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    """在 FastAPI lifespan 启动时调用。"""
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=8,
            open=True,
            kwargs={"autocommit": True},
        )
        await _ensure_tables()


async def _ensure_tables() -> None:
    """确保 Harness 新增表存在（幂等）。

    [2026-08-31] Observability/Memory 层新增：
    - agent_runs：每次答疑的结构化轨迹（检索块/得分/token/延迟）
    - task_state：长任务检查点（生成类任务的阶段进度，支持断点查询）
    """
    await execute(
        """CREATE TABLE IF NOT EXISTS agent_runs (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            question TEXT NOT NULL,
            retrieved JSONB DEFAULT '[]',
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            cited_ids JSONB DEFAULT '[]',
            error TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )"""
    )
    await execute(
        """CREATE TABLE IF NOT EXISTS task_state (
            task_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            ref_id TEXT,
            status TEXT NOT NULL,
            stage TEXT DEFAULT '',
            payload JSONB DEFAULT '{}',
            updated_at TIMESTAMPTZ DEFAULT now()
        )"""
    )
    await execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_conv ON agent_runs (conversation_id)"
    )


async def close_pool() -> None:
    """在 FastAPI lifespan 退出时调用。"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_conn():
    """获取连接的上下文管理器。autocommit 模式，每个语句即提交。"""
    if _pool is None:
        await init_pool()
    async with _pool.connection() as conn:
        yield conn


async def fetch_one(query: str, params: tuple | None = None) -> dict | None:
    async with get_conn() as conn:
        cur = await conn.execute(query, params)
        row = await cur.fetchone()
        if row is None:
            return None
        cols = [d.name for d in cur.description]
        return dict(zip(cols, row, strict=True))


async def fetch_all(query: str, params: tuple | None = None) -> list[dict]:
    async with get_conn() as conn:
        cur = await conn.execute(query, params)
        rows = await cur.fetchall()
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, r, strict=True)) for r in rows]


async def execute(query: str, params: tuple | None = None) -> None:
    async with get_conn() as conn:
        await conn.execute(query, params)


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)
