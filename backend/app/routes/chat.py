from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Recording
from app.schemas import ChatRequest, ChatResponse
from app.services.chat_service import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be blank")
    if request.recording_id and db.get(Recording, request.recording_id) is None:
        raise HTTPException(status_code=404, detail="Session recording not found")
    try:
        answer, evidence = answer_question(question, recording_id=request.recording_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ChatResponse(
        question=question,
        answer=answer,
        evidence=evidence,
        grounded=bool(evidence),
    )
