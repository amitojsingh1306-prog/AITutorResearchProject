"""ChromaDB persistence adapter for chats, messages, and memory stream."""

import hashlib
import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from backend.models.chat import ChatSummary, Message
from backend.models.learner import LearnerProfile, MemoryRecord
from backend.utils.time import parse_timestamp


logger = logging.getLogger(__name__)


class ChatNotFoundError(LookupError):
    """Raised when a requested chat does not exist."""


class ChromaChatRepository:
    """Persist chat metadata and ordered messages in separate collections.

    Keeping storage behind this adapter allows later memory implementations to
    add semantic collections without coupling them to HTTP handlers.
    """

    def __init__(self, persistence_path: Path) -> None:
        persistence_path.mkdir(parents=True, exist_ok=True)
        self._profile_file = persistence_path / "learner_profiles.json"
        self._chat_file = persistence_path / "chats.json"
        self._message_file = persistence_path / "messages.json"
        self._client = chromadb.PersistentClient(path=str(persistence_path))
        self._chats: Collection = self._client.get_or_create_collection(
            name="chats",
            embedding_function=None,
            metadata={"description": "ChatbotTutorAI conversation metadata"},
        )
        self._messages: Collection = self._client.get_or_create_collection(
            name="messages",
            embedding_function=None,
            metadata={"description": "ChatbotTutorAI ordered chat messages"},
        )
        self._learner_profiles: Collection = self._client.get_or_create_collection(
            name="learner_profiles",
            embedding_function=None,
            metadata={"description": "ChatbotTutorAI long-term learner profiles"},
        )
        self._memories: Collection = self._client.get_or_create_collection(
            name="memories",
            embedding_function=None,
            metadata={"description": "ChatbotTutorAI meaningful learner memories"},
        )
        logger.warning(
            "[MEMORY DEBUG] Chroma collection initialized collection=memories count=%s path=%s",
            self._memories.count(),
            persistence_path,
        )

    def save_chat(self, chat: ChatSummary) -> ChatSummary:
        chats = self._read_json_file(self._chat_file)
        chats[chat.id] = chat.model_dump_json()
        self._write_json_file(self._chat_file, chats)
        return chat

    def list_chats(self, user_id: str) -> list[ChatSummary]:
        chats = [
            ChatSummary.model_validate_json(document)
            for document in self._read_json_file(self._chat_file).values()
        ]
        chats = [chat for chat in chats if chat.user_id == user_id]
        return sorted(chats, key=lambda item: item.updated_at, reverse=True)

    def get_chat(self, chat_id: str, user_id: str) -> ChatSummary:
        document = self._read_json_file(self._chat_file).get(chat_id)
        if not document:
            raise ChatNotFoundError(chat_id)
        chat = ChatSummary.model_validate_json(document)
        if chat.user_id != user_id:
            raise ChatNotFoundError(chat_id)
        return chat

    def save_message(self, message: Message) -> Message:
        messages = self._read_json_file(self._message_file)
        messages[message.id] = message.model_dump_json()
        self._write_json_file(self._message_file, messages)
        return message

    def list_messages(self, chat_id: str, user_id: str) -> list[Message]:
        messages = [
            Message.model_validate_json(document)
            for document in self._read_json_file(self._message_file).values()
        ]
        messages = [
            message
            for message in messages
            if message.chat_id == chat_id and message.user_id == user_id
        ]
        return sorted(messages, key=lambda item: item.timestamp)

    def list_user_messages(self, user_id: str) -> list[Message]:
        messages = [
            Message.model_validate_json(document)
            for document in self._read_json_file(self._message_file).values()
        ]
        messages = [message for message in messages if message.user_id == user_id]
        return sorted(messages, key=lambda item: item.timestamp)

    def get_learner_profile(self, user_id: str) -> LearnerProfile:
        profiles = self._read_profile_file()
        document = profiles.get(user_id)
        if not document:
            return LearnerProfile(user_id=user_id)
        return LearnerProfile.model_validate_json(document)

    def save_learner_profile(self, profile: LearnerProfile) -> LearnerProfile:
        profiles = self._read_profile_file()
        profiles[profile.user_id] = profile.model_dump_json()
        self._profile_file.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
        return profile

    def _read_profile_file(self) -> dict[str, str]:
        return self._read_json_file(self._profile_file)

    @staticmethod
    def _read_json_file(path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("[PROFILE DEBUG] Could not read JSON store %s; starting empty", path)
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(key): str(value) for key, value in payload.items()}

    @staticmethod
    def _write_json_file(path: Path, payload: dict[str, str]) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def save_memory(self, memory: MemoryRecord) -> MemoryRecord:
        embedding = memory.embedding or self.embed_text(memory.memory)
        memory = memory.model_copy(update={"embedding": embedding})
        before_count = self._memories.count()
        logger.warning(
            "[MEMORY DEBUG] Storing memory collection=memories before_count=%s type=%s content=%s",
            before_count,
            memory.type,
            self._safe_summary(memory.memory),
        )
        self._memories.upsert(
            ids=[memory.id],
            documents=[memory.model_dump_json()],
            embeddings=[embedding],
            metadatas=[
                {
                    "user_id": memory.user_id,
                    "timestamp": memory.timestamp.isoformat(),
                    "importance": memory.importance,
                    "type": memory.type,
                    "topic": memory.topic or "",
                    "status": memory.status,
                    "source_message_id": memory.source_message_id or "",
                }
            ],
        )
        logger.warning(
            "[MEMORY DEBUG] Stored memory collection=memories after_count=%s id=%s",
            self._memories.count(),
            memory.id,
        )
        return memory

    def list_memories(self, user_id: str) -> list[MemoryRecord]:
        result = self._memories.get(
            where={"user_id": user_id},
            include=["documents"],
        )
        memories = [
            MemoryRecord.model_validate_json(document)
            for document in result.get("documents") or []
            if document
        ]
        return sorted(memories, key=lambda item: item.timestamp)

    def query_memories(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 24,
    ) -> list[tuple[MemoryRecord, float]]:
        logger.warning(
            "[RETRIEVAL DEBUG] Chroma query collection=memories user_id=%s limit=%s query=%s",
            user_id,
            limit,
            self._safe_summary(query),
        )
        result = self._memories.query(
            query_embeddings=[self.embed_text(query)],
            n_results=limit,
            where={"user_id": user_id},
            include=["documents", "distances"],
        )
        documents = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        records: list[tuple[MemoryRecord, float]] = []
        for document, distance in zip(documents, distances, strict=True):
            if not document:
                continue
            relevance = max(0.0, 1.0 - float(distance))
            records.append((MemoryRecord.model_validate_json(document), relevance))
        logger.warning(
            "[RETRIEVAL DEBUG] Chroma returned collection=memories count=%s total_documents=%s",
            len(records),
            self._memories.count(),
        )
        for index, (record, relevance) in enumerate(records, start=1):
            logger.warning(
                "[RETRIEVAL DEBUG] Chroma raw result %s type=%s relevance=%.4f content=%s",
                index,
                record.type,
                relevance,
                self._safe_summary(record.memory),
            )
        return records

    def delete_memory(self, memory_id: str) -> None:
        self._memories.delete(ids=[memory_id])

    def get_json_embedding_collection(self) -> Collection:
        return self._client.get_or_create_collection(
            name="json_message_embeddings",
            embedding_function=None,
            metadata={
                "description": "Derived embeddings copied from JSON chat history",
                "source": str(self._message_file),
            },
        )

    @staticmethod
    def embed_text(text: str, dimensions: int = 64) -> list[float]:
        """Create a deterministic lightweight embedding for local semantic lookup.

        This keeps the architecture ready for a real embedding model while avoiding
        network calls and large model downloads in the current local prototype.
        """

        vector = [0.0] * dimensions
        tokens = [token.lower() for token in text.split() if token.strip()]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % dimensions
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vector[index] += sign

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return [0.0] * dimensions
        return [value / magnitude for value in vector]

    @staticmethod
    def _safe_summary(text: str, max_chars: int = 140) -> str:
        compact = " ".join(text.strip().split())
        if len(compact) <= max_chars:
            return compact
        return f"{compact[: max_chars - 1].rstrip()}..."

    @staticmethod
    def _chat_from_metadata(metadata: dict[str, Any]) -> ChatSummary:
        return ChatSummary(
            id=str(metadata["chat_id"]),
            title=str(metadata["title"]),
            user_id=str(metadata.get("user_id", "legacy-local-user")),
            session_id=str(metadata["session_id"]),
            created_at=parse_timestamp(str(metadata["created_at"])),
            updated_at=parse_timestamp(str(metadata["updated_at"])),
        )

    @staticmethod
    def _message_from_record(
        document: str,
        metadata: dict[str, Any],
    ) -> Message:
        return Message(
            id=str(metadata["message_id"]),
            chat_id=str(metadata["chat_id"]),
            user_id=str(metadata.get("user_id", "legacy-local-user")),
            role=str(metadata["role"]),
            content=document,
            timestamp=parse_timestamp(str(metadata["timestamp"])),
            session_id=str(metadata["session_id"]),
        )
