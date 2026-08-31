"""用户画像 API 路由。"""
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
        raise HTTPException(status_code=400, detail={"code": "E_USER_PROFILE", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "E_INTERNAL", "message": str(e)})
