"""FastAPI dependency providers."""

from fastapi import Request

from backend.services.chat_service import ChatService
from backend.services.profile_service import ProfileService


def get_chat_service(request: Request) -> ChatService:
    """Resolve the application-scoped chat service."""

    return request.app.state.chat_service


def get_profile_service(request: Request) -> ProfileService:
    """Resolve the application-scoped profile/onboarding service."""

    return request.app.state.profile_service
