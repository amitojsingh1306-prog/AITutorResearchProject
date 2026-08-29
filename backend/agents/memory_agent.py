"""Memory agent facade over the MemGPT-inspired memory backend."""

import logging

from backend.database.chroma_repository import ChromaChatRepository
from backend.llm.ollama_client import OllamaClient
from backend.memory.memory_manager import MemoryManager
from backend.memory.memory_store import ChromaVectorMemoryStore
from backend.memory.retrieval import VectorMemoryRetriever
from backend.memory.working_memory import ConversationalBufferMemory
from backend.models.chat import Message
from backend.models.learner import (
    ConversationStateSignal,
    IntentSignal,
    MemoryRecord,
    MemorySignal,
)


logger = logging.getLogger(__name__)


class MemoryAgent:
    """Keep the orchestration contract stable while memory backends evolve.

    The chatbot still calls this agent exactly as before. Internally, it now
    delegates to a modular memory manager with separate working-memory,
    long-term-store, retrieval, and importance-scoring components. That gives
    the research project clean swap points for future benchmarks without
    rewriting the tutor pipeline.
    """

    prompt = (
        "Manage working memory and long-term memory. Promote only important, "
        "stable learner information. Retrieve relevant long-term memories before "
        "the tutor responds."
    )

    def __init__(
        self,
        repository: ChromaChatRepository,
        llm_client: OllamaClient | None = None,
        *,
        working_memory_limit: int = 10,
    ) -> None:
        store = ChromaVectorMemoryStore(repository)
        logger.warning(
            "[MEMORY DEBUG] ChromaVectorMemoryStore initialized successfully: %s",
            store.__class__.__name__,
        )
        self._repository = repository
        self._manager = MemoryManager(
            store=store,
            retriever=VectorMemoryRetriever(store),
            working_memory=ConversationalBufferMemory(max_messages=working_memory_limit),
            llm_client=llm_client,
        )

    def process(
        self,
        *,
        user_message: Message,
        intent: IntentSignal,
        conversation_state: ConversationStateSignal,
    ) -> MemorySignal:
        logger.warning(
            "[MEMORY DEBUG] MemoryAgent.process called user_id=%s chat_id=%s message=%s",
            user_message.user_id,
            user_message.chat_id,
            self._safe_summary(user_message.content),
        )
        conversation_messages = self._repository.list_messages(
            user_message.chat_id,
            user_message.user_id,
        )
        if not conversation_messages or conversation_messages[-1].id != user_message.id:
            conversation_messages.append(user_message)

        return self._manager.process_turn(
            user_message=user_message,
            conversation_messages=conversation_messages,
            intent=intent,
            conversation_state=conversation_state,
        )

    def store_assistant_experience(
        self,
        *,
        assistant_message: Message,
        topic: str,
    ) -> MemoryRecord:
        return self._manager.store_assistant_experience(
            assistant_message=assistant_message,
            topic=topic,
        )

    def list_active_memories(self, user_id: str) -> list[MemoryRecord]:
        return self._manager.list_active_memories(user_id)

    @staticmethod
    def _safe_summary(text: str, max_chars: int = 120) -> str:
        compact = " ".join(text.strip().split())
        if len(compact) <= max_chars:
            return compact
        return f"{compact[: max_chars - 1].rstrip()}..."
