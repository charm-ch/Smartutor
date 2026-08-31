"""EXEC 组路由（M3）：代码沙箱，契约 §3。"""
from fastapi import APIRouter, HTTPException

from app.schemas.execute import ExecuteRequest, ExecuteResponse
from app.services.sandbox import SandboxError, execute

router = APIRouter()


@router.post("", response_model=ExecuteResponse)
async def run_code(payload: ExecuteRequest) -> ExecuteResponse:
    """在隔离容器中编译运行代码（契约 §3.1）。"""
    try:
        outcome = await execute(payload.language, payload.code, payload.stdin)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="M3 沙箱服务未实现") from None
    except SandboxError as e:
        code = str(e)
        if code == "E_TIMEOUT":
            raise HTTPException(status_code=408, detail={"code": "E_TIMEOUT", "message": "运行超时(10s)"}) from None
        if code == "E_LIMIT":
            raise HTTPException(status_code=413, detail={"code": "E_LIMIT", "message": "超出资源限制"}) from None
        raise HTTPException(status_code=500, detail={"code": code, "message": "沙箱错误"}) from None

    return ExecuteResponse(
        run_id=f"run_{outcome.time_ms}",  # TODO(@M3): 用 uuid 生成正式 run_id
        exit_code=outcome.exit_code,
        stdout=outcome.stdout,
        stderr=outcome.stderr,
        time_ms=outcome.time_ms,
    )
