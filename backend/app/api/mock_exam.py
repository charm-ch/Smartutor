"""模拟试卷 API 路由。

[2026-08-31] Harness·Loop：错误响应统一为 {stage, detail, suggestion} 三元组，
明确指出卡在哪个阶段并给出建议动作。
"""
from fastapi import APIRouter, HTTPException

from app.schemas.mock_exam import MockExamRequest, MockExamResponse
from app.services import mock_exam

router = APIRouter()


@router.post("", response_model=MockExamResponse)
async def create_mock_exam(payload: MockExamRequest) -> MockExamResponse:
    """基于历年真题生成模拟试题。"""
    try:
        result = await mock_exam.generate_mock_exam(
            kb_id=payload.kb_id,
            num_questions=payload.num_questions,
            difficulty=payload.difficulty,
            include_answers=payload.include_answers,
        )
        return MockExamResponse(**result)
    except mock_exam.MockExamError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "E_MOCK_EXAM",
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
