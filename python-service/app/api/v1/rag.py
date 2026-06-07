from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import BaseResponse, success_response
from app.schemas.rag import RagAskRequest, RagVisualAskRequest
from app.services.visual_qa_service import answer_rag_question, answer_visual_question

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/ask", response_model=BaseResponse, summary="Ask question with RAG")
def ask_rag_endpoint(request: RagAskRequest) -> BaseResponse:
    return success_response(answer_rag_question(request))


@router.post("/visual-ask", response_model=BaseResponse, summary="Ask visual question with page text and visual summary")
def ask_visual_rag_endpoint(request: RagVisualAskRequest) -> BaseResponse:
    return success_response(answer_visual_question(request))
