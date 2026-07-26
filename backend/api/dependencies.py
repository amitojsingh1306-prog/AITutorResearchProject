"""FastAPI dependency providers."""

from fastapi import Request

from backend.services.chat_service import ChatService


def get_chat_service(request: Request) -> ChatService:
    """Resolve the application-scoped chat service."""

    return request.app.state.chat_service
