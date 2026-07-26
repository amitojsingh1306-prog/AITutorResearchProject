"""Periodic reflection over the learner memory stream."""

from datetime import datetime, timezone
from uuid import uuid4

from backend.database.chroma_repository import ChromaChatRepository
from backend.models.learner import MemoryRecord, MemorySignal, ReflectionSignal


class ReflectionAgent:
    """Generate higher-level insights after enough important memories accumulate."""

    prompt = (
        "Inspect important raw memories and produce higher-level learner insights "
        "as JSON reflection memories. Do not answer the user."
    )

    important_memory_interval = 4

    def __init__(self, repository: ChromaChatRepository) -> None:
        self._repository = repository

    def reflect(self, user_id: str, memory: MemorySignal) -> ReflectionSignal:
        all_memories = self._repository.list_memories(user_id)
        important = [
            item
            for item in all_memories
            if item.importance >= 7 and item.type != "reflection"
        ]
        reflections = [item for item in all_memories if item.type == "reflection"]

        next_threshold = (len(reflections) + 1) * self.important_memory_interval
        if len(important) < next_threshold:
            return ReflectionSignal(
                triggered=False,
                insights=[],
                reason="Not enough important memories for a new reflection.",
            )

        insight_text = self._insight_from_memories(important[-8:])
        topic = memory.profile.current_topics[-1] if memory.profile.current_topics else None
        record = MemoryRecord(
            id=str(uuid4()),
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            memory=insight_text,
            importance=9,
            type="reflection",
            topic=topic,
            status="active",
        )
        stored = self._repository.save_memory(record)
        return ReflectionSignal(
            triggered=True,
            insights=[stored],
            reason="Important memory threshold reached.",
        )

    def _insight_from_memories(self, memories: list[MemoryRecord]) -> str:
        text = " ".join(memory.memory.lower() for memory in memories)
        if "implementation" in text or "build" in text or "coding" in text:
            return "Reflection: The user learns best through hands-on implementation and concrete examples."
        if "confused" in text or "struggled" in text:
            return "Reflection: The user benefits from prerequisite repair before progressing."
        if "goal" in text or "engineer" in text:
            return "Reflection: The user's long-term motivation should guide examples and practice tasks."
        return "Reflection: The learner benefits when lessons continue from recent progress instead of restarting."
