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

    _memory_triggers = (
        "my name is",
        "remember",
        "i am ",
        "i'm ",
        "i study",
        "i like",
        "i prefer",
        "i want",
        "my goal",
        "confused",
        "weak",
        "mistake",
    )

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
            for chunk in self._direct_stream_reply(user_message):
                chunks.append(chunk)
                yield self._sse("chunk", {"content": chunk})
            if not chunks:
                fallback_reply = self._direct_reply(user_message)
                chunks.append(fallback_reply)
                yield self._sse("chunk", {"content": fallback_reply})
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
            return self._direct_reply(user_message)
        except OllamaClientError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM request failed: {error}",
            ) from error

    def _direct_reply(self, user_message: Message) -> str:
        if self._llm_client is None:
            return "Backend is running, but no model provider is configured."
        return self._llm_client.generate_reply(
            self._prompt_messages(user_message),
            system_prompt=self._system_prompt(user_message),
        )

    def _direct_stream_reply(self, user_message: Message) -> Iterator[str]:
        if self._llm_client is None:
            yield "Backend is running, but no model provider is configured."
            return
        yield from self._llm_client.stream_reply(
            self._prompt_messages(user_message),
            system_prompt=self._system_prompt(user_message),
        )

    def _prompt_messages(self, user_message: Message) -> list[Message]:
        history = [
            message
            for message in self._repository.list_messages(
                user_message.chat_id,
                user_message.user_id,
            )
            if message.id != user_message.id
        ]
        return [*history[-8:], user_message]

    def _system_prompt(self, user_message: Message) -> str:
        memory_lines = self._memory_lines(user_message)
        return "\n".join(
            [
                "You are ChatbotTutorAI, a helpful educational tutor.",
                "Answer clearly and briefly. Use simple examples when useful.",
                "Use the recent chat history and saved memory notes for continuity.",
                "If the user asks what you remember or what was discussed, answer from the provided history/memory only.",
                "If the answer is not in history or memory, say you do not have that saved yet.",
                "",
                "Saved memory notes:",
                *(memory_lines or ["- No saved memory notes yet."]),
            ]
        )

    def _memory_lines(self, user_message: Message) -> list[str]:
        messages = self._repository.list_user_messages(user_message.user_id)
        lines: list[str] = []
        for message in messages:
            content = " ".join(message.content.split())
            if (
                message.role == "user"
                and len(content) >= 3
                and any(trigger in content.lower() for trigger in self._memory_triggers)
            ):
                lines.append(f"- User said: {content[:240]}")
        return lines[-12:]

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
