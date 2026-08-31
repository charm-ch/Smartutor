"""用户画像 API 路由。

[2026-08-31] Harness·Loop：错误响应统一为 {stage, detail, suggestion} 三元组。
"""
from fastapi import APIRouter, HTTPException

from app.schemas.user_profile import UserProfileRequest, UserProfileResponse
from app.services import user_profile

router = APIRouter()


@router.post("", response_model=UserProfileResponse)
async def create_user_profile(payload: UserProfileRequest) -> UserProfileResponse:
    """基于对话历史生成个性化学习画像。"""
    try:
        result = await user_profile.generate_user_profile(
            conversation_id=payload.conversation_id
        )
        return UserProfileResponse(**result)
    except user_profile.UserProfileError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "E_USER_PROFILE",
                "stage": e.stage,
                "detail": str(e),
                "suggestion": e.suggestion,
            },
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={
                "code": "E_INTERNAL",
                "stage": "unknown",
                "detail": str(e)[:200],
                "suggestion": "请稍后重试；若持续失败请查看服务端日志",
            },
        )
