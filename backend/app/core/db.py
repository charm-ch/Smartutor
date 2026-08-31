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
