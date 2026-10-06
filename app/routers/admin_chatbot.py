from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps.admin_auth import require_admin
from app.models.chatbot import ChatbotSession, ChatbotWorkflow
from app.routers.chatbot import get_or_create_default_workflow
from app.schemas.chatbot import (
    DEFAULT_WORKFLOW,
    ChatbotMessageOut,
    ChatbotSessionDetail,
    ChatbotSessionListItem,
    ChatbotWorkflowOut,
    ChatbotWorkflowUpdate,
)

router = APIRouter(prefix="/admin/chatbot", tags=["Admin Chatbot"])


@router.get("/workflow", response_model=ChatbotWorkflowOut, dependencies=[Depends(require_admin)])
def admin_get_workflow(db: Session = Depends(get_db)):
    workflow = get_or_create_default_workflow(db)
    return ChatbotWorkflowOut(
        slug=workflow.slug,
        enabled=bool(workflow.enabled),
        data=workflow.data or DEFAULT_WORKFLOW,
        updated_at=workflow.updated_at.isoformat() if workflow.updated_at else None,
    )


@router.put("/workflow", response_model=ChatbotWorkflowOut, dependencies=[Depends(require_admin)])
def admin_update_workflow(payload: ChatbotWorkflowUpdate, db: Session = Depends(get_db)):
    workflow = get_or_create_default_workflow(db)
    workflow.enabled = 1 if payload.enabled else 0
    workflow.data = payload.data or DEFAULT_WORKFLOW
    db.commit()
    db.refresh(workflow)
    return ChatbotWorkflowOut(
        slug=workflow.slug,
        enabled=bool(workflow.enabled),
        data=workflow.data or DEFAULT_WORKFLOW,
        updated_at=workflow.updated_at.isoformat() if workflow.updated_at else None,
    )


@router.get("/sessions", response_model=list[ChatbotSessionListItem], dependencies=[Depends(require_admin)])
def admin_list_sessions(db: Session = Depends(get_db), limit: int = 100):
    sessions = (
        db.query(ChatbotSession)
        .order_by(ChatbotSession.updated_at.desc())
        .limit(min(max(limit, 1), 200))
        .all()
    )
    return [
        ChatbotSessionListItem(
            id=item.id,
            session_key=item.session_key,
            visitor_path=item.visitor_path,
            preview=item.preview,
            status=item.status,
            message_count=item.message_count,
            started_at=item.started_at.isoformat() if item.started_at else "",
            updated_at=item.updated_at.isoformat() if item.updated_at else "",
        )
        for item in sessions
    ]


@router.get(
    "/sessions/{session_id}",
    response_model=ChatbotSessionDetail,
    dependencies=[Depends(require_admin)],
)
def admin_get_session(session_id: int, db: Session = Depends(get_db)):
    session = (
        db.query(ChatbotSession)
        .options(joinedload(ChatbotSession.messages))
        .filter(ChatbotSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    return ChatbotSessionDetail(
        id=session.id,
        session_key=session.session_key,
        visitor_path=session.visitor_path,
        preview=session.preview,
        status=session.status,
        message_count=session.message_count,
        started_at=session.started_at.isoformat() if session.started_at else "",
        updated_at=session.updated_at.isoformat() if session.updated_at else "",
        messages=[
            ChatbotMessageOut(
                id=message.id,
                role=message.role,
                text=message.text,
                options=message.options_json,
                created_at=message.created_at.isoformat() if message.created_at else "",
            )
            for message in session.messages
        ],
    )


@router.patch("/sessions/{session_id}/archive", dependencies=[Depends(require_admin)])
def admin_archive_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatbotSession).filter(ChatbotSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    session.status = "archived"
    db.commit()
    return {"status": "ok"}


@router.delete("/sessions/{session_id}", dependencies=[Depends(require_admin)])
def admin_delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatbotSession).filter(ChatbotSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    db.delete(session)
    db.commit()
    return {"status": "ok"}
