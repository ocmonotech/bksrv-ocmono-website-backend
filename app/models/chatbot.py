from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ChatbotWorkflow(Base):
    __tablename__ = "chatbot_workflows"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(80), nullable=False, unique=True, index=True, default="default")
    enabled = Column(Integer, nullable=False, default=1)  # 1/0 for MySQL compatibility
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ChatbotSession(Base):
    __tablename__ = "chatbot_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_key = Column(String(80), nullable=False, unique=True, index=True)
    visitor_path = Column(String(500), nullable=True)
    preview = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="open")  # open | closed | archived
    message_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    messages = relationship(
        "ChatbotMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatbotMessage.id",
    )


class ChatbotMessage(Base):
    __tablename__ = "chatbot_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chatbot_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user | bot
    text = Column(Text, nullable=False)
    options_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    session = relationship("ChatbotSession", back_populates="messages")
