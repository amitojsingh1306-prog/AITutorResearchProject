"""Learner-profile endpoints backing the pre-chat onboarding survey."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from backend.api.dependencies import get_profile_service
from backend.models.auth import OnboardingRequest, OnboardingResponse
from backend.models.learner import LearnerProfile
from backend.services.profile_service import ProfileService


router = APIRouter(prefix="/profile", tags=["profile"])
ProfileServiceDependency = Annotated[ProfileService, Depends(get_profile_service)]
UserIdHeader = Annotated[str, Header(alias="X-User-Id", min_length=1, max_length=120)]


@router.get("", response_model=LearnerProfile)
def get_profile(service: ProfileServiceDependency, user_id: UserIdHeader) -> LearnerProfile:
    """Return the caller's learner profile, including onboarding_complete.

    The frontend calls this right after login to decide whether to show the
    onboarding survey before the chat opens.
    """

    return service.get_profile(user_id)


@router.post(
    "/onboarding",
    response_model=OnboardingResponse,
    status_code=status.HTTP_200_OK,
)
def complete_onboarding(
    payload: OnboardingRequest,
    service: ProfileServiceDependency,
    user_id: UserIdHeader,
) -> OnboardingResponse:
    """Save the survey answers the chatbot collects before the first chat."""

    profile = service.complete_onboarding(user_id, payload)
    return OnboardingResponse(profile=profile)
