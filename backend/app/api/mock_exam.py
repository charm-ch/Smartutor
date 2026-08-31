"""模拟试卷 API 路由。"""
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
        raise HTTPException(status_code=400, detail={"code": "E_MOCK_EXAM", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "E_INTERNAL", "message": str(e)})
