"""Chat lifecycle and messaging endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from backend.api.dependencies import get_chat_service
from backend.models.chat import (
    ChatCreateRequest,
    ChatDetail,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSummary,
)
from backend.services.chat_service import ChatService


router = APIRouter(prefix="/chat", tags=["chat"])
ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]
UserIdHeader = Annotated[str, Header(alias="X-User-Id", min_length=1, max_length=120)]


@router.post(
    "/create",
    response_model=ChatSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_chat(
    payload: ChatCreateRequest,
    service: ChatServiceDependency,
    user_id: UserIdHeader,
) -> ChatSummary:
    """Create an empty conversation."""

    return service.create_chat(payload, user_id)


@router.get("/list", response_model=list[ChatSummary])
def list_chats(service: ChatServiceDependency, user_id: UserIdHeader) -> list[ChatSummary]:
    """List conversations, most recently updated first."""

    return service.list_chats(user_id)


@router.get("/{chat_id}", response_model=ChatDetail)
def get_chat(
    chat_id: str,
    service: ChatServiceDependency,
    user_id: UserIdHeader,
) -> ChatDetail:
    """Return one conversation and its ordered messages."""

    return service.get_chat(chat_id, user_id)


@router.post(
    "/{chat_id}/message",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_message(
    chat_id: str,
    payload: ChatMessageRequest,
    service: ChatServiceDependency,
    user_id: UserIdHeader,
) -> ChatMessageResponse:
    """Store a user message and the Phase 1 placeholder assistant reply."""

    return service.add_message(chat_id, payload, user_id)
