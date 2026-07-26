"""Chat orchestration independent of the HTTP layer."""

from uuid import uuid4

from fastapi import HTTPException, status

from backend.database.chroma_repository import (
    ChatNotFoundError,
    ChromaChatRepository,
)
from backend.llm.groq_client import GroqClient, GroqClientError
from backend.models.chat import (
    ChatCreateRequest,
    ChatDetail,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSummary,
    Message,
)
from backend.orchestration.tutor_orchestrator import TutorOrchestrator
from backend.utils.time import utc_now


class ChatService:
    """Coordinate chat creation, retrieval, and placeholder responses."""

    def __init__(
        self,
        repository: ChromaChatRepository,
        llm_client: GroqClient | None = None,
    ) -> None:
        self._repository = repository
        self._llm_client = llm_client
        self._orchestrator = TutorOrchestrator(repository, llm_client)

    def create_chat(self, payload: ChatCreateRequest, user_id: str) -> ChatSummary:
        now = utc_now()
        chat = ChatSummary(
            id=str(uuid4()),
            title=payload.title.strip(),
            user_id=user_id,
            session_id=payload.session_id or str(uuid4()),
            created_at=now,
            updated_at=now,
        )
        return self._repository.save_chat(chat)

    def list_chats(self, user_id: str) -> list[ChatSummary]:
        return self._repository.list_chats(user_id)

    def get_chat(self, chat_id: str, user_id: str) -> ChatDetail:
        chat = self._get_existing_chat(chat_id, user_id)
        return ChatDetail(
            **chat.model_dump(),
            messages=self._repository.list_messages(chat_id, user_id),
        )

    def add_message(
        self,
        chat_id: str,
        payload: ChatMessageRequest,
        user_id: str,
    ) -> ChatMessageResponse:
        chat = self._get_existing_chat(chat_id, user_id)
        session_id = payload.session_id or chat.session_id
        user_message = self._new_message(
            chat_id=chat.id,
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=payload.content.strip(),
        )
        self._repository.save_message(user_message)

        assistant_content = self._assistant_reply(chat.id, user_message)
        assistant_message = self._new_message(
            chat_id=chat.id,
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=assistant_content,
        )

        self._repository.save_message(assistant_message)
        self._orchestrator.record_assistant_reply(assistant_message)

        updated_title = chat.title
        if chat.title == "New conversation":
            updated_title = self._title_from_message(user_message.content)
        updated_chat = chat.model_copy(
            update={"title": updated_title, "updated_at": assistant_message.timestamp}
        )
        self._repository.save_chat(updated_chat)

        return ChatMessageResponse(
            user_message=user_message,
            assistant_message=assistant_message,
            chat=updated_chat,
        )

    def _assistant_reply(self, chat_id: str, user_message: Message) -> str:
        try:
            return self._orchestrator.generate_reply(chat_id, user_message)
        except GroqClientError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Groq request failed: {error}",
            ) from error

    def _get_existing_chat(self, chat_id: str, user_id: str) -> ChatSummary:
        try:
            return self._repository.get_chat(chat_id, user_id)
        except ChatNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found.",
            ) from error

    @staticmethod
    def _new_message(
        *,
        chat_id: str,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
    ) -> Message:
        return Message(
            id=str(uuid4()),
            chat_id=chat_id,
            user_id=user_id,
            role=role,
            content=content,
            timestamp=utc_now(),
            session_id=session_id,
        )

    @staticmethod
    def _title_from_message(content: str) -> str:
        words = content.split()
        title = " ".join(words[:7])
        return f"{title}…" if len(words) > 7 else title
