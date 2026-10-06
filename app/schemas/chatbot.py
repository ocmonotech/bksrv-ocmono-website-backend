from typing import Any, Optional

from pydantic import BaseModel, Field


DEFAULT_WORKFLOW = {
    "welcome_message": "Hi! How can I help you today?",
    "support_phone": "+918850533614",
    "whatsapp": "918850533614",
    "nudge_enabled": True,
    "nudge_delay_seconds": 22,
    "main_menu": [
        {"id": "guide", "label": "Guide me around", "action": "guide"},
        {"id": "demo", "label": "Book a demo", "action": "demo"},
        {"id": "pricing", "label": "Pricing & plans", "action": "pricing"},
        {"id": "specialty", "label": "Find my specialty", "action": "specialty"},
        {"id": "contact", "label": "Contact support", "action": "contact"},
    ],
}


class ChatbotMessageIn(BaseModel):
    role: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=8000)
    options: Optional[list[Any]] = None


class ChatbotSessionSyncRequest(BaseModel):
    session_key: str = Field(min_length=4, max_length=80)
    visitor_path: Optional[str] = Field(default=None, max_length=500)
    messages: list[ChatbotMessageIn] = Field(default_factory=list)


class ChatbotAskHistoryItem(BaseModel):
    role: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=4000)


class ChatbotAskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatbotAskHistoryItem] = Field(default_factory=list)
    visitor_path: Optional[str] = Field(default=None, max_length=500)


class ChatbotAskResponse(BaseModel):
    reply: str
    options: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "openai"


class ChatbotMessageOut(BaseModel):
    id: int
    role: str
    text: str
    options: Optional[list[Any]] = None
    created_at: str


class ChatbotSessionListItem(BaseModel):
    id: int
    session_key: str
    visitor_path: Optional[str] = None
    preview: Optional[str] = None
    status: str
    message_count: int
    started_at: str
    updated_at: str


class ChatbotSessionDetail(ChatbotSessionListItem):
    messages: list[ChatbotMessageOut] = Field(default_factory=list)


class ChatbotWorkflowOut(BaseModel):
    slug: str
    enabled: bool
    data: dict[str, Any]
    updated_at: Optional[str] = None


class ChatbotWorkflowUpdate(BaseModel):
    enabled: bool = True
    data: dict[str, Any]
