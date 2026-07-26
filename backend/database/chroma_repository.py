"""ChromaDB persistence adapter for chats, messages, and memory stream."""

import hashlib
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from backend.models.chat import ChatSummary, Message
from backend.models.learner import LearnerProfile, MemoryRecord
from backend.utils.time import parse_timestamp


class ChatNotFoundError(LookupError):
    """Raised when a requested chat does not exist."""


class ChromaChatRepository:
    """Persist chat metadata and ordered messages in separate collections.

    Keeping storage behind this adapter allows later memory implementations to
    add semantic collections without coupling them to HTTP handlers.
    """

    def __init__(self, persistence_path: Path) -> None:
        persistence_path.mkdir(parents=True, exist_ok=True)
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
        self._memory_stream: Collection = self._client.get_or_create_collection(
            name="memory_stream",
            embedding_function=None,
            metadata={"description": "ChatbotTutorAI meaningful learner memories"},
        )

    def save_chat(self, chat: ChatSummary) -> ChatSummary:
        metadata = {
            "chat_id": chat.id,
            "title": chat.title,
            "user_id": chat.user_id,
            "session_id": chat.session_id,
            "created_at": chat.created_at.isoformat(),
            "updated_at": chat.updated_at.isoformat(),
        }
        self._chats.upsert(
            ids=[chat.id],
            documents=[chat.title],
            # Phase 1 performs no semantic search. A fixed vector keeps ChromaDB
            # in storage-only mode without loading its default ONNX embedder.
            embeddings=[[0.0]],
            metadatas=[metadata],
        )
        return chat

    def list_chats(self, user_id: str) -> list[ChatSummary]:
        result = self._chats.get(where={"user_id": user_id}, include=["metadatas"])
        chats = [
            self._chat_from_metadata(metadata)
            for metadata in result.get("metadatas") or []
            if metadata is not None
        ]
        return sorted(chats, key=lambda item: item.updated_at, reverse=True)

    def get_chat(self, chat_id: str, user_id: str) -> ChatSummary:
        result = self._chats.get(ids=[chat_id], include=["metadatas"])
        metadata_items = result.get("metadatas") or []
        if not metadata_items or metadata_items[0] is None:
            raise ChatNotFoundError(chat_id)
        chat = self._chat_from_metadata(metadata_items[0])
        if chat.user_id != user_id:
            raise ChatNotFoundError(chat_id)
        return chat

    def save_message(self, message: Message) -> Message:
        metadata = {
            "chat_id": message.chat_id,
            "message_id": message.id,
            "user_id": message.user_id,
            "role": message.role,
            "timestamp": message.timestamp.isoformat(),
            "session_id": message.session_id,
        }
        self._messages.add(
            ids=[message.id],
            documents=[message.content],
            embeddings=[[0.0]],
            metadatas=[metadata],
        )
        return message

    def list_messages(self, chat_id: str, user_id: str) -> list[Message]:
        result = self._messages.get(
            where={"$and": [{"chat_id": chat_id}, {"user_id": user_id}]},
            include=["documents", "metadatas"],
        )
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        messages = [
            self._message_from_record(document, metadata)
            for document, metadata in zip(documents, metadatas, strict=True)
            if metadata is not None
        ]
        return sorted(messages, key=lambda item: item.timestamp)

    def list_user_messages(self, user_id: str) -> list[Message]:
        result = self._messages.get(
            where={"user_id": user_id},
            include=["documents", "metadatas"],
        )
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        messages = [
            self._message_from_record(document, metadata)
            for document, metadata in zip(documents, metadatas, strict=True)
            if metadata is not None
        ]
        return sorted(messages, key=lambda item: item.timestamp)

    def get_learner_profile(self, user_id: str) -> LearnerProfile:
        result = self._learner_profiles.get(ids=[user_id], include=["documents"])
        documents = result.get("documents") or []
        if not documents:
            return LearnerProfile(user_id=user_id)
        return LearnerProfile.model_validate_json(documents[0])

    def save_learner_profile(self, profile: LearnerProfile) -> LearnerProfile:
        self._learner_profiles.upsert(
            ids=[profile.user_id],
            documents=[profile.model_dump_json()],
            embeddings=[[0.0]],
            metadatas=[{"user_id": profile.user_id}],
        )
        return profile

    def save_memory(self, memory: MemoryRecord) -> MemoryRecord:
        embedding = memory.embedding or self.embed_text(memory.memory)
        memory = memory.model_copy(update={"embedding": embedding})
        self._memory_stream.upsert(
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
        return memory

    def list_memories(self, user_id: str) -> list[MemoryRecord]:
        result = self._memory_stream.get(
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
        result = self._memory_stream.query(
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
        return records

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
