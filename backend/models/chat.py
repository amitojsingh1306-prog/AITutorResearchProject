"""Typed chat domain schemas exposed by the API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatCreateRequest(BaseModel):
    """Inputs accepted when creating a conversation."""

    title: str = Field(default="New conversation", min_length=1, max_length=120)
    session_id: str | None = Field(default=None, min_length=1, max_length=120)


class ChatSummary(BaseModel):
    """Chat metadata used by the conversation list."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    user_id: str
    session_id: str
    created_at: datetime
    updated_at: datetime


class Message(BaseModel):
    """A persisted conversation message."""

    id: str
    chat_id: str
    user_id: str
    role: str
    content: str
    timestamp: datetime
    session_id: str


class ChatDetail(ChatSummary):
    """Complete conversation returned when a chat is opened."""

    messages: list[Message]


class ChatMessageRequest(BaseModel):
    """User message sent to a conversation."""

    content: str = Field(min_length=1, max_length=20_000)
    session_id: str | None = Field(default=None, min_length=1, max_length=120)


class ChatMessageResponse(BaseModel):
    """Both messages created during a Phase 1 request."""

    user_message: Message
    assistant_message: Message
    chat: ChatSummary
