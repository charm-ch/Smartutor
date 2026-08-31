"""Runs 组路由（Harness·Observability/Memory）：

- GET /api/runs/{run_id}/trace   单次答疑的结构化轨迹（检索块/得分/token/延迟/引用）
- GET /api/runs/stats            近 N 次答疑的平均延迟与 token 消耗
- GET /api/tasks/{task_id}       生成类任务（模拟卷/画像）的检查点进度

[2026-08-31] 源自自检结论：此前仅 journalctl，无法还原单次请求的完整决策链。
"""
from fastapi import APIRouter, HTTPException

from app.core import db

router = APIRouter()


@router.get("/{run_id}/trace")
async def get_run_trace(run_id: str) -> dict:
    """还原单次答疑轨迹：检索了哪些块及得分 → token 用量 → 延迟 → 实际引用块 id。"""
    row = await db.fetch_one(
        """SELECT id, conversation_id, question, retrieved, prompt_tokens,
                  completion_tokens, latency_ms, cited_ids, error, created_at
           FROM agent_runs WHERE id=%s""",
        (run_id,),
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "E_NOT_FOUND", "message": f"轨迹 {run_id} 不存在"},
        )
    return {
        "run_id": row["id"],
        "conversation_id": row["conversation_id"],
        "question": row["question"],
        "retrieved": row["retrieved"] or [],
        "prompt_tokens": row["prompt_tokens"],
        "completion_tokens": row["completion_tokens"],
        "latency_ms": row["latency_ms"],
        "cited_ids": row["cited_ids"] or [],
        "error": row["error"],
        "created_at": row["created_at"].isoformat(),
    }


@router.get("/stats")
async def get_run_stats(limit: int = 20) -> dict:
    """近 N 次答疑的平均延迟与 token 消耗（成本可见）。"""
    limit = max(1, min(limit, 200))
    rows = await db.fetch_all(
        """SELECT prompt_tokens, completion_tokens, latency_ms, (error IS NOT NULL) AS has_error
           FROM agent_runs ORDER BY created_at DESC LIMIT %s""",
        (limit,),
    )
    total = len(rows)
    if total == 0:
        return {"total": 0, "avg_latency_ms": 0, "prompt_tokens": 0,
                "completion_tokens": 0, "error_count": 0}
    return {
        "total": total,
        "avg_latency_ms": round(sum(r["latency_ms"] or 0 for r in rows) / total),
        "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in rows),
        "completion_tokens": sum(r["completion_tokens"] or 0 for r in rows),
        "error_count": sum(1 for r in rows if r["has_error"]),
    }


@router.get("/tasks/{task_id}")
async def get_task_state(task_id: str) -> dict:
    """查询生成类任务的检查点进度（进程重启后仍可查）。"""
    row = await db.fetch_one(
        """SELECT task_id, kind, ref_id, status, stage, payload, updated_at
           FROM task_state WHERE task_id=%s""",
        (task_id,),
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "E_NOT_FOUND", "message": f"任务 {task_id} 不存在（可能已过期清理）"},
        )
    return {
        "task_id": row["task_id"],
        "kind": row["kind"],
        "ref_id": row["ref_id"],
        "status": row["status"],
        "stage": row["stage"],
        "payload": row["payload"] or {},
        "updated_at": row["updated_at"].isoformat(),
    }
