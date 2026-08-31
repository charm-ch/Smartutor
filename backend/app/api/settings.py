"""设置组路由：API 配置管理（USTC LLM 平台）。

遵循平台文档建议：API Key 保存在服务端（data/settings.json），
前端只读脱敏值；测试连接由后端代理发起。
"""
import httpx
from fastapi import APIRouter, HTTPException

from app.core import settings_store
from app.schemas.settings import SettingsOut, SettingsPayload, TestRequest, TestResponse

router = APIRouter()


@router.get("", response_model=SettingsOut)
async def get_settings() -> SettingsOut:
    """读取当前生效配置（脱敏返回，API Key 不落前端）。"""
    eff = settings_store.effective_settings()
    api_key = str(eff.get("api_key") or "")
    return SettingsOut(
        base_url=str(eff.get("api_base_url") or ""),
        chat_model=str(eff.get("chat_model") or ""),
        vision_model=str(eff.get("vision_model") or ""),
        embedding_model=str(eff.get("embedding_model") or ""),
        embedding_use_local=bool(eff.get("embedding_use_local", True)),
        api_key_masked=settings_store.mask_api_key(api_key),
        has_api_key=bool(api_key),
    )


@router.post("", response_model=SettingsOut)
async def save_settings(payload: SettingsPayload) -> SettingsOut:
    """保存配置。api_key 为空则保留旧值。"""
    current = settings_store.store.load()
    new = {
        "api_base_url": payload.base_url.rstrip("/"),
        "chat_model": payload.chat_model,
        "vision_model": payload.vision_model,
        "embedding_model": payload.embedding_model,
        "embedding_use_local": payload.embedding_use_local,
    }
    if payload.api_key:
        new["api_key"] = payload.api_key
    else:
        new["api_key"] = current.get("api_key", "")

    settings_store.store.save(new)
    return await get_settings()


@router.post("/test", response_model=TestResponse)
async def test_connection(payload: TestRequest) -> TestResponse:
    """测试 API 连通性：请求 {base_url}/models 拉取可用模型列表（不保存）。"""
    base_url = payload.base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {payload.api_key}"},
            )
        if resp.status_code == 401:
            return TestResponse(ok=False, message="API Key 错误或失效 (401)")
        if resp.status_code == 403:
            return TestResponse(ok=False, message="无模型调用权限 (403)")
        if resp.status_code == 404:
            return TestResponse(ok=False, message="请求地址错误 (404)，请检查 Base URL")
        if resp.status_code == 429:
            return TestResponse(ok=False, message="请求过多或超过额度 (429)")
        resp.raise_for_status()
        data = resp.json()
        models = sorted(m["id"] for m in data.get("data", []))
        if not models:
            return TestResponse(ok=False, message="连接成功，但未返回模型列表")
        return TestResponse(ok=True, models=models, message=f"连接成功，共 {len(models)} 个模型")
    except httpx.TimeoutException:
        return TestResponse(ok=False, message="连接超时，请检查 Base URL 与网络")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"code": "E_INTERNAL", "message": str(e)}) from e
