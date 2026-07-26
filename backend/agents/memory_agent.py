"""Memory stream storage and retrieval inspired by Generative Agents."""

import math
import re
from datetime import datetime, timezone
from uuid import uuid4

from backend.database.chroma_repository import ChromaChatRepository
from backend.models.chat import Message
from backend.models.learner import (
    ConversationStateSignal,
    IntentSignal,
    LearnerProfile,
    MemoryRecord,
    MemorySignal,
    RetrievedMemory,
)


class MemoryAgent:
    """Store meaningful experiences and retrieve memories by scored diffusion."""

    prompt = (
        "Extract meaningful learner experiences as JSON memories. Assign "
        "importance 1-10, memory type, topic, and status. Retrieve memories "
        "using recency + importance + semantic relevance."
    )

    _known_topic_aliases = {
        "langgraph": "LangGraph",
        "stategraph": "StateGraph",
        "conditional edges": "Conditional Edges",
        "nodes": "Nodes",
        "edges": "Edges",
        "rag": "RAG",
        "fastapi": "FastAPI",
        "chromadb": "ChromaDB",
        "python": "Python",
        "nlp": "NLP",
    }

    def __init__(self, repository: ChromaChatRepository) -> None:
        self._repository = repository

    def process(
        self,
        *,
        user_message: Message,
        intent: IntentSignal,
        conversation_state: ConversationStateSignal,
    ) -> MemorySignal:
        profile = self._repository.get_learner_profile(user_message.user_id)
        stored_memories = self._store_user_experiences(
            user_message,
            intent,
            conversation_state,
        )
        profile = self._update_profile(profile, stored_memories, intent)
        self._repository.save_learner_profile(profile)

        retrieved_memories = self._retrieve_scored(
            user_id=user_message.user_id,
            query=f"{intent.raw_text} {intent.topic or ''}",
        )
        return MemorySignal(
            profile=profile,
            stored_memories=stored_memories,
            retrieved_memories=retrieved_memories,
        )

    def store_assistant_experience(
        self,
        *,
        assistant_message: Message,
        topic: str,
    ) -> MemoryRecord:
        memory = MemoryRecord(
            id=str(uuid4()),
            user_id=assistant_message.user_id,
            timestamp=assistant_message.timestamp,
            memory=f"Tutor taught or reinforced {topic}.",
            importance=4,
            type="tutor_action",
            topic=topic,
            status="active",
            source_message_id=assistant_message.id,
        )
        return self._repository.save_memory(memory)

    def _store_user_experiences(
        self,
        user_message: Message,
        intent: IntentSignal,
        conversation_state: ConversationStateSignal,
    ) -> list[MemoryRecord]:
        topic = self._topic_from_intent_or_text(intent)
        memory_type = self._memory_type(conversation_state, user_message.content)
        importance = self._importance(user_message.content, conversation_state)
        status = self._status(conversation_state)
        topics = self._topics_from_text(user_message.content)
        if not topics or memory_type not in {"understanding", "learning_event"}:
            topics = [topic]

        stored: list[MemoryRecord] = []
        for item in topics:
            memory = MemoryRecord(
                id=str(uuid4()),
                user_id=user_message.user_id,
                timestamp=user_message.timestamp,
                memory=self._memory_text(
                    user_message.content,
                    intent,
                    conversation_state,
                    item,
                ),
                importance=importance,
                type=memory_type,
                topic=item,
                status=status,
                source_message_id=user_message.id,
            )
            stored.append(self._repository.save_memory(memory))
        return stored

    def _retrieve_scored(self, *, user_id: str, query: str) -> list[RetrievedMemory]:
        now = datetime.now(timezone.utc)
        candidates = self._repository.query_memories(user_id=user_id, query=query)
        scored: list[RetrievedMemory] = []

        for record, relevance in candidates:
            age_hours = max(0.0, (now - record.timestamp).total_seconds() / 3600)
            recency_score = math.exp(-age_hours / 72)
            importance_score = record.importance / 10
            relevance_score = relevance
            total_score = recency_score + importance_score + relevance_score
            scored.append(
                RetrievedMemory(
                    record=record,
                    recency_score=round(recency_score, 4),
                    importance_score=round(importance_score, 4),
                    relevance_score=round(relevance_score, 4),
                    total_score=round(total_score, 4),
                )
            )

        return sorted(scored, key=lambda item: item.total_score, reverse=True)[:8]

    def _update_profile(
        self,
        profile: LearnerProfile,
        memories: list[MemoryRecord],
        intent: IntentSignal,
    ) -> LearnerProfile:
        goals = list(profile.learning_goals)
        completed = list(profile.completed_topics)
        current = list(profile.current_topics)
        interests = list(profile.interests)
        mistakes = list(profile.previous_mistakes)
        style = profile.preferred_explanation_style

        for memory in memories:
            topic = memory.topic
            text = memory.memory.lower()
            if topic and memory.type in {"goal", "learning_event"}:
                goals = self._append_unique(goals, [topic])
                current = self._append_unique(current, [topic])
                interests = self._append_unique(interests, [topic])
            if topic and (
                memory.type == "understanding"
                or memory.memory.lower().startswith("user learned")
            ):
                completed = self._append_unique(completed, [topic])
            if topic and memory.type == "struggle":
                mistakes = self._append_unique(mistakes, [topic])
            if "implementation" in text or "coding example" in text:
                style = "hands-on implementation"

        if intent.topic and all(memory.type not in {"social", "emotion"} for memory in memories):
            current = self._append_unique(current, [intent.topic])

        return profile.model_copy(
            update={
                "learning_goals": goals[-10:],
                "completed_topics": completed[-20:],
                "current_topics": current[-6:],
                "preferred_explanation_style": style,
                "previous_mistakes": mistakes[-10:],
                "interests": interests[-10:],
            }
        )

    def _memory_text(
        self,
        content: str,
        intent: IntentSignal,
        state: ConversationStateSignal,
        topic: str | None,
    ) -> str:
        lowered = content.lower()
        if state.state == "gratitude":
            return "User thanked the tutor."
        if state.state == "excitement":
            return "User expressed excitement about the lesson."
        if state.state == "greeting":
            return "User greeted the tutor."
        if state.state == "conversation_end":
            return "User ended the conversation."
        if state.state == "understanding":
            return f"User understood {topic or 'the current topic'}."
        if state.state == "confused":
            return f"User struggled with {topic or 'the current topic'}."
        if state.state == "topic_switch":
            return f"User switched learning path to {topic or intent.raw_text}."
        if "goal" in lowered or "want to become" in lowered:
            return f"User goal: {content.strip()}"
        if any(phrase in lowered for phrase in ("i prefer", "i like", "implementation", "example")):
            return f"User preference: {content.strip()}"
        if any(phrase in lowered for phrase in ("i learned", "i know", "completed")):
            return f"User learned {topic or content.strip()}."
        return f"User is learning {topic or intent.raw_text}."

    def _memory_type(self, state: ConversationStateSignal, content: str) -> str:
        lowered = content.lower()
        if state.state in {"gratitude", "greeting", "conversation_end"}:
            return "social"
        if state.state == "excitement":
            return "emotion"
        if state.state == "understanding":
            return "understanding"
        if state.state == "confused":
            return "struggle"
        if state.state == "topic_switch":
            return "topic_switch"
        if "goal" in lowered or "want to become" in lowered:
            return "goal"
        if any(phrase in lowered for phrase in ("prefer", "like", "hate", "dislike")):
            return "preference"
        return "learning_event"

    def _importance(self, content: str, state: ConversationStateSignal) -> int:
        lowered = content.lower()
        if state.state in {"gratitude", "greeting", "conversation_end"}:
            return 2
        if state.state == "excitement":
            return 4
        if "want to become" in lowered or "goal" in lowered:
            return 10
        if state.state == "understanding":
            return 9
        if state.state == "confused":
            return 8
        if any(word in lowered for word in ("hate", "prefer", "dislike")):
            return 8
        if any(word in lowered for word in ("learned", "understand", "implemented")):
            return 7
        if "learning" in lowered:
            return 6
        return 4

    def _status(self, state: ConversationStateSignal) -> str:
        if state.state == "skip":
            return "skipped"
        if state.state == "understanding":
            return "completed"
        if state.state == "confused":
            return "needs_review"
        return "active"

    def _topic_from_intent_or_text(self, intent: IntentSignal) -> str | None:
        if intent.topic:
            return self._canonical_topic(intent.topic)
        return self._canonical_topic(intent.raw_text)

    def _canonical_topic(self, text: str) -> str | None:
        topics = self._topics_from_text(text)
        return topics[-1] if topics else text.strip()[:80] or None

    def _topics_from_text(self, text: str) -> list[str]:
        lowered = text.lower()
        return [
            canonical
            for alias, canonical in self._known_topic_aliases.items()
            if re.search(rf"\b{re.escape(alias)}\b", lowered)
        ]

    @staticmethod
    def _append_unique(current: list[str], items: list[str]) -> list[str]:
        result = [item for item in current if item]
        seen = {item.lower() for item in result}
        for item in items:
            normalized = item.strip()
            if normalized and normalized.lower() not in seen:
                result.append(normalized)
                seen.add(normalized.lower())
        return result
