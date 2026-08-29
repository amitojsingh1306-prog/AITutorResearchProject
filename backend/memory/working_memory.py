"""Working-memory strategies for the active conversation.

In MemGPT terms, working memory is the limited context visible to the model
right now. It is not the full chat database and it is not long-term memory.
This educational implementation uses a conversational buffer: the latest N
messages from the current chat are selected for the next response and older
messages are discarded from the active context, while still remaining in normal
chat history.
"""

from __future__ import annotations

from typing import Protocol

from backend.memory.hygiene import is_low_signal_text, is_memory_control_request
from backend.models.chat import Message


class WorkingMemory(Protocol):
    """Interface for benchmarkable working-memory strategies."""

    def select_context(self, messages: list[Message]) -> list[Message]:
        """Return the messages that fit in the active context window."""


class ConversationalBufferMemory:
    """Simple last-N-message buffer.

    This is the baseline memory strategy for experiments. Later research
    variants can implement the same interface with rolling summaries, graph
    context, or hybrid context assembly without changing the chatbot code.
    """

    def __init__(self, max_messages: int = 10) -> None:
        self.max_messages = max(1, max_messages)

    def select_context(self, messages: list[Message]) -> list[Message]:
        if not messages:
            return []

        latest = messages[-1]
        useful_prior_messages = [
            message
            for message in messages[:-1]
            if not self._is_context_noise(message)
        ]
        return [*useful_prior_messages, latest][-self.max_messages :]

    @staticmethod
    def _is_context_noise(message: Message) -> bool:
        if message.role != "user":
            return False
        return is_low_signal_text(message.content) or is_memory_control_request(
            message.content
        )


class RollingSummaryMemory:
    """Placeholder interface-compatible strategy for future benchmarking.

    A rolling-summary strategy would compress older turns into a short summary
    before appending recent raw messages. It is intentionally not implemented
    yet because the current research milestone needs a clean baseline first.
    """

    def __init__(self, fallback: WorkingMemory | None = None) -> None:
        self._fallback = fallback or ConversationalBufferMemory()

    def select_context(self, messages: list[Message]) -> list[Message]:
        return self._fallback.select_context(messages)
