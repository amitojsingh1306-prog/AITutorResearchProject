"""Chat orchestration independent of the HTTP layer."""

import json
from collections.abc import Iterator
from uuid import uuid4

from fastapi import HTTPException, status

from backend.database.chroma_repository import (
    ChatNotFoundError,
    ChromaChatRepository,
)
from backend.llm.ollama_client import OllamaClient, OllamaClientError
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
        llm_client: OllamaClient | None = None,
        *,
        working_memory_limit: int = 10,
    ) -> None:
        self._repository = repository
        self._llm_client = llm_client
        self._orchestrator = TutorOrchestrator(
            repository,
            llm_client,
            working_memory_limit=working_memory_limit,
        )

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

    def stream_message(
        self,
        chat_id: str,
        payload: ChatMessageRequest,
        user_id: str,
    ) -> Iterator[str]:
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

        assistant_message = self._new_message(
            chat_id=chat.id,
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content="",
        )

        yield self._sse("user_message", user_message.model_dump(mode="json"))
        yield self._sse(
            "assistant_message_start",
            assistant_message.model_dump(mode="json"),
        )

        chunks: list[str] = []
        try:
            for chunk in self._orchestrator.stream_reply(chat.id, user_message):
                chunks.append(chunk)
                yield self._sse("chunk", {"content": chunk})
        except OllamaClientError as error:
            yield self._sse("error", {"detail": f"LLM request failed: {error}"})
            return

        assistant_content = "".join(chunks)
        assistant_message = assistant_message.model_copy(
            update={"content": assistant_content}
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

        yield self._sse(
            "done",
            {
                "assistant_message": assistant_message.model_dump(mode="json"),
                "chat": updated_chat.model_dump(mode="json"),
            },
        )

    def _assistant_reply(self, chat_id: str, user_message: Message) -> str:
        try:
            return self._orchestrator.generate_reply(chat_id, user_message)
        except OllamaClientError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM request failed: {error}",
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

    @staticmethod
    def _sse(event: str, data: object) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"
