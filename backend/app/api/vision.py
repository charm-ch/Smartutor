"""VISION 组路由（M4）：视觉识别，契约 §4。"""
from fastapi import APIRouter, HTTPException

from app.schemas.vision import VisionRequest, VisionResponse
from app.services.vision import VisionError, analyze

router = APIRouter()


@router.post("/analyze", response_model=VisionResponse)
async def analyze_image(payload: VisionRequest) -> VisionResponse:
    """识别报错截图，提取 code / error（契约 §4.1）。"""
    try:
        result = await analyze(payload.image_url)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="M4 视觉服务未实现") from None
    except VisionError as e:
        raise HTTPException(status_code=422, detail={"code": "E_VISION", "message": str(e)}) from None

    return VisionResponse(text=result.text, code=result.code, error=result.error)
