"""Long-term memory storage interfaces.

MemGPT keeps information outside the immediate prompt and retrieves it when it
becomes relevant. This module defines that external-memory boundary. The
current implementation adapts the existing ChromaDB repository, but the tutor
only depends on the protocol, so vector, graph, and hybrid stores can be
benchmarked later behind the same methods.
"""

from __future__ import annotations

from typing import Protocol

from backend.database.chroma_repository import ChromaChatRepository
from backend.models.learner import LearnerProfile, MemoryRecord


class LongTermMemoryStore(Protocol):
    """Minimal store contract used by the memory manager."""

    def get_learner_profile(self, user_id: str) -> LearnerProfile:
        """Load persistent learner metadata."""

    def save_learner_profile(self, profile: LearnerProfile) -> LearnerProfile:
        """Persist learner metadata."""

    def save_memory(self, memory: MemoryRecord) -> MemoryRecord:
        """Persist one important long-term memory item."""

    def delete_memory(self, memory_id: str) -> None:
        """Delete one long-term memory item."""

    def list_memories(self, user_id: str) -> list[MemoryRecord]:
        """Return all persisted memories for reflection or analysis."""

    def query_memories(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 24,
    ) -> list[tuple[MemoryRecord, float]]:
        """Return candidate memories and raw relevance scores."""


class ChromaVectorMemoryStore:
    """Vector long-term memory backed by the existing ChromaDB repository."""

    def __init__(self, repository: ChromaChatRepository) -> None:
        self._repository = repository

    def get_learner_profile(self, user_id: str) -> LearnerProfile:
        return self._repository.get_learner_profile(user_id)

    def save_learner_profile(self, profile: LearnerProfile) -> LearnerProfile:
        return self._repository.save_learner_profile(profile)

    def save_memory(self, memory: MemoryRecord) -> MemoryRecord:
        return self._repository.save_memory(memory)

    def delete_memory(self, memory_id: str) -> None:
        self._repository.delete_memory(memory_id)

    def list_memories(self, user_id: str) -> list[MemoryRecord]:
        return self._repository.list_memories(user_id)

    def query_memories(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 24,
    ) -> list[tuple[MemoryRecord, float]]:
        return self._repository.query_memories(user_id=user_id, query=query, limit=limit)


class GraphMemoryStore:
    """Interface placeholder for a future graph-memory benchmark."""

    benchmark_name = "graph_memory"


class HybridMemoryStore:
    """Interface placeholder for a future vector-plus-graph benchmark."""

    benchmark_name = "hybrid_memory"
