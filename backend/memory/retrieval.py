"""Long-term memory retrieval and ranking.

Before each tutor response, MemGPT-style systems search external memory and
bring only useful items back into the active prompt. This module keeps that
retrieval policy separate from storage. The current ranker combines vector
relevance, importance, and recency; future experiments can replace it with
graph traversal, hybrid scoring, or learned retrieval.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Protocol

from backend.models.learner import RetrievedMemory

from .hygiene import is_polluted_memory_text
from .memory_store import LongTermMemoryStore


logger = logging.getLogger(__name__)


class MemoryRetriever(Protocol):
    """Interface for benchmarkable retrieval strategies."""

    def retrieve(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 8,
    ) -> list[RetrievedMemory]:
        """Return prompt-ready long-term memories relevant to the current turn."""


class VectorMemoryRetriever:
    """Vector-memory retriever with structured filtering and reranking."""

    _profile_memory_types = {
        "fact",
        "goal",
        "preference",
        "achievement",
        "learning_style",
        "profile",
    }
    _blocked_prompt_types = {
        "conversation_event",
        "reflection",
        "temporary",
        "temporary_context",
    }

    def __init__(
        self,
        store: LongTermMemoryStore,
        *,
        candidate_limit: int = 20,
        recency_half_life_hours: float = 72.0,
        min_relevance_score: float = 0.18,
    ) -> None:
        self._store = store
        self._candidate_limit = candidate_limit
        self._recency_half_life_hours = recency_half_life_hours
        self._min_relevance_score = min_relevance_score

    def retrieve(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 8,
    ) -> list[RetrievedMemory]:
        logger.warning(
            "[RETRIEVAL DEBUG] VectorMemoryRetriever running user_id=%s limit=%s candidate_limit=%s query=%s",
            user_id,
            limit,
            self._candidate_limit,
            self._safe_summary(query),
        )
        now = datetime.now(timezone.utc)
        candidates = self._store.query_memories(
            user_id=user_id,
            query=query,
            limit=self._candidate_limit,
        )
        logger.warning(
            "[RETRIEVAL DEBUG] Semantic search candidates returned=%s",
            len(candidates),
        )
        query_profile = self._query_profile(query)
        logger.warning(
            "[RETRIEVAL DEBUG] Query profile mode=%s allowed_types=%s focus_terms=%s terms=%s",
            query_profile["mode"],
            sorted(query_profile["allowed_types"]),
            sorted(query_profile["focus_terms"]),
            sorted(query_profile["terms"]),
        )
        scored: list[RetrievedMemory] = []

        for record, relevance in candidates:
            logger.warning(
                "[RETRIEVAL DEBUG] Candidate memory type=%s relevance=%.4f topic=%s content=%s",
                record.type,
                relevance,
                record.topic or "",
                self._safe_summary(record.memory),
            )
            if is_polluted_memory_text(record.memory):
                self._log_filtered(record, "polluted_or_control_memory")
                continue
            if self._is_conversation_event_memory(record.memory):
                self._log_filtered(record, "conversation_event_memory")
                continue
            if not self._metadata_allows(record.type, query_profile["allowed_types"]):
                self._log_filtered(record, "disallowed_memory_type")
                continue
            if query_profile["mode"] == "profile" and self._is_temporary_knowledge_state(record.type, record.memory):
                self._log_filtered(record, "temporary_knowledge_state_for_profile_query")
                continue
            lexical_score = self._lexical_score(
                query_profile["terms"],
                self._memory_terms(record.memory, record.topic or "", record.type),
            )
            focus_score = self._lexical_score(
                query_profile["focus_terms"],
                self._memory_terms(record.memory, record.topic or "", record.type),
            )
            if query_profile["focus_terms"] and focus_score <= 0:
                self._log_filtered(record, "missing_focus_terms")
                continue

            age_hours = max(0.0, (now - record.timestamp).total_seconds() / 3600)
            recency_score = math.exp(-age_hours / self._recency_half_life_hours)
            importance_score = record.importance / 10
            relevance_score = max(relevance, lexical_score)
            type_score = 1.0 if record.type in query_profile["allowed_types"] else 0.5
            total_score = (
                (0.45 * lexical_score)
                + (0.25 * relevance_score)
                + (0.15 * importance_score)
                + (0.10 * recency_score)
                + (0.05 * type_score)
            )
            if total_score < self._min_relevance_score:
                self._log_filtered(record, f"below_relevance_threshold:{total_score:.4f}")
                continue
            scored.append(
                RetrievedMemory(
                    record=record,
                    recency_score=round(recency_score, 4),
                    importance_score=round(importance_score, 4),
                    relevance_score=round(relevance_score, 4),
                    total_score=round(total_score, 4),
                )
            )

        selected = sorted(scored, key=lambda item: item.total_score, reverse=True)[:limit]
        logger.warning(
            "[RETRIEVAL DEBUG] Retrieved memories after filtering/reranking count=%s",
            len(selected),
        )
        for index, item in enumerate(selected, start=1):
            logger.warning(
                "[RETRIEVAL DEBUG] Retrieved memory %s type=%s score=%.4f topic=%s content=%s",
                index,
                item.record.type,
                item.total_score,
                item.record.topic or "",
                self._safe_summary(item.record.memory),
            )
        return selected

    @classmethod
    def _query_profile(cls, query: str) -> dict[str, set[str] | str]:
        terms = cls._terms(query)
        focus_terms = cls._focus_terms(query)
        lowered = query.lower()
        if cls._is_personal_profile_query(lowered):
            mode = "profile"
            allowed_types = cls._profile_memory_types
            focus_terms = set()
        elif cls._is_knowledge_query(lowered):
            mode = "knowledge"
            allowed_types = {"knowledge_state"}
        elif re.search(r"\b(?:prefer|preference|style)\b", lowered):
            mode = "preference"
            allowed_types = {"preference"}
        elif re.search(r"\b(?:goal|dream|target|preparing|prepare)\b", lowered):
            mode = "goal"
            allowed_types = {"goal", "achievement", "knowledge_state"}
        elif re.search(r"\b(?:struggle|confused|weak|difficulty|stuck)\b", lowered):
            mode = "difficulty"
            allowed_types = {"learning_difficulty"}
        elif re.search(r"\b(?:topics?|covered|discussed|learned|list)\b", lowered):
            mode = "topic_history"
            allowed_types = {"knowledge_state", "achievement", "fact"}
        else:
            mode = "general"
            allowed_types = {
                "goal",
                "knowledge_state",
                "learning_difficulty",
                "preference",
                "achievement",
                "fact",
            }
        return {
            "mode": mode,
            "terms": terms,
            "focus_terms": focus_terms,
            "allowed_types": allowed_types,
        }

    @classmethod
    def _metadata_allows(cls, memory_type: str, allowed_types: set[str] | str) -> bool:
        normalized_type = cls._normalize_memory_type(memory_type)
        if normalized_type in cls._blocked_prompt_types:
            return False
        return normalized_type in allowed_types

    @staticmethod
    def _normalize_memory_type(memory_type: str) -> str:
        return memory_type.strip().lower().replace("-", "_").replace(" ", "_")

    @classmethod
    def _is_temporary_knowledge_state(cls, memory_type: str, memory: str) -> bool:
        if cls._normalize_memory_type(memory_type) != "knowledge_state":
            return False
        return bool(
            re.search(
                r"\b(?:asked|request(?:ed)?|question|explain|what is|teach|discussed|covered)\b",
                memory,
                re.I,
            )
        )

    @staticmethod
    def _is_conversation_event_memory(memory: str) -> bool:
        return bool(
            re.search(
                r"\b(?:user|student)\s+(?:asked|requested|said|told|mentioned)\b",
                memory,
                re.I,
            )
            or re.search(
                r"\b(?:another user|previous request|conversation event|transcript)\b",
                memory,
                re.I,
            )
        )

    @staticmethod
    def _is_personal_profile_query(lowered_query: str) -> bool:
        return bool(
            re.search(r"\b(?:about me|profile)\b", lowered_query)
            or re.search(r"\bwhat\b.*\b(?:remember|know|learned)\b.*\bme\b", lowered_query)
            or re.search(r"\bwhat\b.*\b(?:goals?|preferences?|learning style)\b", lowered_query)
            or re.search(r"\b(?:my goals?|my preferences?|my learning style)\b", lowered_query)
            or re.search(r"\bwhat\b.*\bprojects?\b.*\b(?:worked on|built|made|implemented|done)\b", lowered_query)
            or re.search(r"\bwhich\b.*\bprojects?\b.*\b(?:worked on|built|made|implemented|done)\b", lowered_query)
        )

    @staticmethod
    def _is_knowledge_query(lowered_query: str) -> bool:
        return bool(
            re.search(r"\b(?:explain|teach|describe)\b", lowered_query)
            or re.search(r"^what\s+is\b", lowered_query)
            or re.search(r"^how\s+does\b.*\bwork\b", lowered_query)
        )

    @classmethod
    def _log_filtered(cls, record: object, reason: str) -> None:
        memory_type = getattr(record, "type", "")
        topic = getattr(record, "topic", "") or ""
        memory = getattr(record, "memory", "")
        logger.warning(
            "[RETRIEVAL DEBUG] Filtered candidate reason=%s type=%s topic=%s content=%s",
            reason,
            memory_type,
            topic,
            cls._safe_summary(memory),
        )

    @classmethod
    def _focus_terms(cls, query: str) -> set[str]:
        lowered = query.lower()
        match = re.search(r"\b(?:in|about|for)\s+([a-z0-9+#. ]+?)[?.!]*$", lowered)
        if not match:
            return set()
        return cls._terms(match.group(1))

    @classmethod
    def _memory_terms(cls, memory: str, topic: str, memory_type: str) -> set[str]:
        return cls._terms(" ".join([memory, topic, memory_type]))

    @staticmethod
    def _terms(text: str) -> set[str]:
        normalized = text.lower().replace("operating systems", "operating system os")
        normalized = normalized.replace("operating system", "operating system os")
        stopwords = {
            "a",
            "an",
            "and",
            "are",
            "covered",
            "did",
            "for",
            "in",
            "is",
            "list",
            "me",
            "of",
            "the",
            "to",
            "topics",
            "topic",
            "u",
            "we",
            "what",
            "which",
        }
        return {
            token
            for token in re.sub(r"[^a-z0-9+#. ]+", " ", normalized).split()
            if len(token) > 1 and token not in stopwords
        }

    @staticmethod
    def _lexical_score(query_terms: set[str], memory_terms: set[str]) -> float:
        if not query_terms:
            return 0.0
        overlap = len(query_terms & memory_terms)
        return overlap / len(query_terms)

    @staticmethod
    def _safe_summary(text: str, max_chars: int = 140) -> str:
        compact = " ".join(text.strip().split())
        if len(compact) <= max_chars:
            return compact
        return f"{compact[: max_chars - 1].rstrip()}..."


class GraphMemoryRetriever:
    """Placeholder retrieval strategy for a future graph-memory benchmark."""

    benchmark_name = "graph_memory"


class HybridMemoryRetriever:
    """Placeholder retrieval strategy for future vector-plus-graph retrieval."""

    benchmark_name = "hybrid_memory"
