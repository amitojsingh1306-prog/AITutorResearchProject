"""Login and onboarding-survey request schemas."""

from pydantic import BaseModel, Field, field_validator

from backend.models.learner import LearnerProfile


class LoginRequest(BaseModel):
    """Payload sent once the client-side identity panel is submitted."""

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def _looks_like_email(cls, value: str) -> str:
        # Kept dependency-free (no email-validator extra) for this local
        # prototype; the frontend's <input type="email"> already does the
        # heavier lifting of validation before this ever gets called.
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("must be a valid email address")
        return normalized


class LoginResponse(BaseModel):
    """Result of a login: the caller mainly needs onboarding_complete."""

    profile: LearnerProfile
    onboarding_complete: bool
    confirmation_email_sent: bool


class OnboardingRequest(BaseModel):
    """Answers collected by the pre-chat onboarding survey.

    Mirrors the six intro questions the tutor asks a first-time user:
    name, field of study, subjects/topics, current level, learning style,
    and goals for the tutor.
    """

    name: str = Field(min_length=1, max_length=120)
    field_of_study: str = Field(min_length=1, max_length=200)
    topics_of_interest: list[str] = Field(default_factory=list)
    skill_level: str = Field(min_length=1, max_length=60)
    preferred_explanation_style: str = Field(min_length=1, max_length=120)
    goals: list[str] = Field(default_factory=list)


class OnboardingResponse(BaseModel):
    """Updated profile returned after the survey is saved."""

    profile: LearnerProfile
