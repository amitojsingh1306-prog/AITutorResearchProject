"""Knowledge framing for personalized tutor responses."""

from backend.models.learner import (
    ConversationStateSignal,
    IntentSignal,
    KnowledgeSignal,
    MemorySignal,
)


class KnowledgeAgent:
    """Frame the current topic using retrieved memory and conversation state."""

    prompt = (
        "Given intent, state, and retrieved memories, produce JSON knowledge "
        "framing: topic, prerequisites, avoid_repeating, and knowledge_notes."
    )

    def enrich(
        self,
        *,
        intent: IntentSignal,
        conversation_state: ConversationStateSignal,
        memory: MemorySignal,
    ) -> KnowledgeSignal:
        topic = intent.topic or (
            memory.profile.current_topics[-1]
            if memory.profile.current_topics
            else "the current topic"
        )
        retrieved_text = " ".join(
            item.record.memory for item in memory.retrieved_memories
        ).lower()

        prerequisites = [
            item
            for item in memory.profile.completed_topics
            if item.lower() in retrieved_text or item in memory.profile.completed_topics
        ]
        avoid_repeating: list[str] = []
        notes: list[str] = []

        if "langgraph" in retrieved_text or "LangGraph" in memory.profile.learning_goals:
            notes.append(
                "LangGraph refers to the framework for stateful LLM workflows, not graph neural networks."
            )

        if conversation_state.state == "confused":
            notes.append("Repair prerequisites before introducing new material.")

        if prerequisites:
            avoid_repeating.append("full beginner reset")

        framing = (
            "continue_from_memory"
            if memory.retrieved_memories and conversation_state.state != "confused"
            else "repair_or_introduce"
        )

        return KnowledgeSignal(
            topic=topic,
            framing=framing,
            prerequisites=prerequisites[-6:],
            avoid_repeating=avoid_repeating,
            knowledge_notes=notes,
        )
