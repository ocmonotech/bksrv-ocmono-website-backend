from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chatbot import ChatbotMessage, ChatbotSession, ChatbotWorkflow
from app.schemas.chatbot import (
    DEFAULT_WORKFLOW,
    ChatbotAskRequest,
    ChatbotAskResponse,
    ChatbotSessionSyncRequest,
    ChatbotWorkflowOut,
)
from app.services.chatbot_ai import ask_openai, openai_enabled

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


def get_or_create_default_workflow(db: Session) -> ChatbotWorkflow:
    workflow = db.query(ChatbotWorkflow).filter(ChatbotWorkflow.slug == "default").first()
    if workflow:
        return workflow

    workflow = ChatbotWorkflow(slug="default", enabled=1, data=DEFAULT_WORKFLOW)
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


@router.get("/workflow", response_model=ChatbotWorkflowOut)
def get_public_workflow(db: Session = Depends(get_db)):
    workflow = get_or_create_default_workflow(db)
    data = dict(workflow.data or DEFAULT_WORKFLOW)
    data["ai_enabled"] = openai_enabled()
    return ChatbotWorkflowOut(
        slug=workflow.slug,
        enabled=bool(workflow.enabled),
        data=data,
        updated_at=workflow.updated_at.isoformat() if workflow.updated_at else None,
    )


@router.post("/ask", response_model=ChatbotAskResponse)
def ask_chatbot(payload: ChatbotAskRequest):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required")

    if not openai_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI chatbot is not configured. Set OPENAI_API_KEY on the backend.",
        )

    try:
        result = ask_openai(
            message=message,
            history=[{"role": item.role, "text": item.text} for item in payload.history],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to get an AI reply right now: {exc}",
        ) from exc

    return ChatbotAskResponse(
        reply=result["reply"],
        options=result.get("options") or [],
        source=result.get("source") or "openai",
    )


@router.post("/sessions/sync")
def sync_chatbot_session(payload: ChatbotSessionSyncRequest, db: Session = Depends(get_db)):
    """Upsert a visitor chat session and replace its messages (admin history)."""
    has_user = any(item.role == "user" for item in payload.messages)
    if not has_user:
        return {"status": "ignored", "reason": "no_user_messages"}

    preview = ""
    for item in reversed(payload.messages):
        if item.text.strip():
            preview = item.text.strip()[:480]
            break

    session = (
        db.query(ChatbotSession)
        .filter(ChatbotSession.session_key == payload.session_key)
        .first()
    )

    if not session:
        session = ChatbotSession(
            session_key=payload.session_key,
            visitor_path=payload.visitor_path,
            preview=preview,
            status="open",
            message_count=len(payload.messages),
        )
        db.add(session)
        db.flush()
    else:
        session.visitor_path = payload.visitor_path or session.visitor_path
        session.preview = preview or session.preview
        session.message_count = len(payload.messages)
        session.status = "open"
        db.query(ChatbotMessage).filter(ChatbotMessage.session_id == session.id).delete()

    for item in payload.messages:
        db.add(
            ChatbotMessage(
                session_id=session.id,
                role=item.role if item.role in ("user", "bot") else "bot",
                text=item.text,
                options_json=item.options,
            )
        )

    db.commit()
    db.refresh(session)
    return {
        "status": "ok",
        "id": session.id,
        "session_key": session.session_key,
        "message_count": session.message_count,
    }
