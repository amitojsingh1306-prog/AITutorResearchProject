"""Login endpoint: records identity and sends a confirmation email."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from backend.api.dependencies import get_profile_service
from backend.models.auth import LoginRequest, LoginResponse
from backend.services.profile_service import ProfileService


router = APIRouter(prefix="/auth", tags=["auth"])
ProfileServiceDependency = Annotated[ProfileService, Depends(get_profile_service)]
UserIdHeader = Annotated[str, Header(alias="X-User-Id", min_length=1, max_length=120)]


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(
    payload: LoginRequest,
    service: ProfileServiceDependency,
    user_id: UserIdHeader,
) -> LoginResponse:
    """Persist the logged-in user's identity and send a confirmation email.

    This is a local-prototype identity layer (no password check happens on
    the backend); the client already derived ``user_id`` from the email. A
    failed email send never fails the login itself.
    """

    profile, email_sent = service.login(user_id, payload)
    return LoginResponse(
        profile=profile,
        onboarding_complete=profile.onboarding_complete,
        confirmation_email_sent=email_sent,
    )
