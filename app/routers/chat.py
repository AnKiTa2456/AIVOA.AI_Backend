from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud
from app.agent.agent import run_agent
from app.database import get_db
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    crud.save_chat_message(db, payload.session_id, "user", payload.message)

    result = run_agent(payload.session_id, payload.message)

    crud.save_chat_message(db, payload.session_id, "assistant", result["reply"])

    return ChatResponse(
        session_id=payload.session_id,
        reply=result["reply"],
        tool_calls=result["tool_calls"],
        interaction=result["interaction"],
    )


@router.get("/{session_id}/history")
def chat_history(session_id: str, db: Session = Depends(get_db)):
    from app.models import ChatMessage

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in messages]
