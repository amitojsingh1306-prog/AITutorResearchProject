"""Login and onboarding-survey orchestration, independent of the HTTP layer."""

from backend.database.chroma_repository import ChromaChatRepository
from backend.models.auth import LoginRequest, OnboardingRequest
from backend.models.learner import LearnerProfile
from backend.utils.email_service import EmailService


class ProfileService:
    """Coordinates the learner-profile knowledge base used to personalize the tutor."""

    def __init__(
        self,
        repository: ChromaChatRepository,
        email_service: EmailService,
    ) -> None:
        self._repository = repository
        self._email_service = email_service

    def login(self, user_id: str, payload: LoginRequest) -> tuple[LearnerProfile, bool]:
        """Record who just logged in and send a login confirmation email.

        Returns the (possibly newly created) profile and whether the
        confirmation email was actually handed off to an SMTP server.
        """

        profile = self._repository.get_learner_profile(user_id)
        profile = profile.model_copy(update={"name": payload.name, "email": payload.email})
        self._repository.save_learner_profile(profile)

        email_sent = self._email_service.send_login_confirmation(
            name=payload.name, email=payload.email
        )
        return profile, email_sent

    def get_profile(self, user_id: str) -> LearnerProfile:
        return self._repository.get_learner_profile(user_id)

    def complete_onboarding(self, user_id: str, answers: OnboardingRequest) -> LearnerProfile:
        """Save the pre-chat survey answers as the learner's long-term profile."""

        profile = self._repository.get_learner_profile(user_id)
        profile = profile.model_copy(
            update={
                "name": answers.name,
                "field_of_study": answers.field_of_study,
                "current_topics": answers.topics_of_interest,
                "skill_level": answers.skill_level,
                "preferred_explanation_style": answers.preferred_explanation_style,
                "learning_goals": answers.goals,
                "onboarding_complete": True,
            }
        )
        return self._repository.save_learner_profile(profile)
