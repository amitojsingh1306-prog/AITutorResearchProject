"""LLM provider that uses Groq first and Ollama as fallback."""

from collections.abc import Iterator
from dataclasses import dataclass
import logging

from backend.llm.groq_client import GroqClient, GroqClientError
from backend.llm.ollama_client import OllamaClient, OllamaClientError
from backend.models.chat import Message


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FallbackLlmClient:
    """Preserve the existing LLM interface while choosing providers internally."""

    primary: GroqClient
    fallback: OllamaClient | None = None

    def generate_reply(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> str:
        try:
            response = self.primary.generate_reply(messages, system_prompt)
            logger.info("LLM provider handled request: groq")
            return response
        except GroqClientError as error:
            logger.warning("Groq failed; falling back to Ollama Qwen: %s", error)
            if self.fallback is None:
                raise OllamaClientError(f"Groq failed and Ollama fallback is disabled: {error}") from error
            response = self.fallback.generate_reply(messages, system_prompt)
            logger.info("LLM provider handled request: ollama_qwen")
            return response

    def stream_reply(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> Iterator[str]:
        yielded_primary_chunk = False
        try:
            for chunk in self.primary.stream_reply(messages, system_prompt):
                yielded_primary_chunk = True
                yield chunk
            logger.info("LLM provider handled streaming request: groq")
        except GroqClientError as error:
            if yielded_primary_chunk:
                raise OllamaClientError(
                    f"Groq streaming failed after output began: {error}"
                ) from error
            logger.warning("Groq streaming failed; falling back to Ollama Qwen: %s", error)
            if self.fallback is None:
                raise OllamaClientError(f"Groq failed and Ollama fallback is disabled: {error}") from error
            yield from self.fallback.stream_reply(messages, system_prompt)
            logger.info("LLM provider handled streaming request: ollama_qwen")

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.0,
    ) -> str:
        try:
            response = self.primary.generate_text(
                system_prompt=system_prompt,
                user_content=user_content,
                temperature=temperature,
            )
            logger.info("LLM provider handled text request: groq")
            return response
        except GroqClientError as error:
            logger.warning("Groq text request failed; falling back to Ollama Qwen: %s", error)
            if self.fallback is None:
                raise OllamaClientError(f"Groq failed and Ollama fallback is disabled: {error}") from error
            response = self.fallback.generate_text(
                system_prompt=system_prompt,
                user_content=user_content,
                temperature=temperature,
            )
            logger.info("LLM provider handled text request: ollama_qwen")
            return response
