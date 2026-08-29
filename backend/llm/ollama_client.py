"""Ollama chat client for local Qwen models."""

from dataclasses import dataclass
import json
from collections.abc import Iterator

import httpx

from backend.models.chat import Message


class OllamaClientError(RuntimeError):
    """Raised when Ollama cannot produce a usable response."""


@dataclass(frozen=True)
class OllamaClient:
    """Minimal Ollama REST client with the app's existing LLM interface."""

    base_url: str
    model: str
    keep_alive: str = "30m"
    num_predict: int = 700
    timeout_seconds: float = 60.0

    def generate_reply(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> str:
        return self._chat(
            [
                {
                    "role": "system",
                    "content": system_prompt or self._default_system_prompt(),
                },
                *self._messages_for_ollama(messages),
            ],
            temperature=0.7,
        )

    def stream_reply(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> Iterator[str]:
        yield from self._chat_stream(
            [
                {
                    "role": "system",
                    "content": system_prompt or self._default_system_prompt(),
                },
                *self._messages_for_ollama(messages),
            ],
            temperature=0.7,
        )

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.0,
    ) -> str:
        return self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=temperature,
        )

    def _chat(self, messages: list[dict[str, str]], *, temperature: float) -> str:
        response = httpx.post(
            f"{self.base_url.rstrip('/')}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "keep_alive": self.keep_alive,
                "options": {
                    "temperature": temperature,
                    "num_predict": self.num_predict,
                },
            },
            timeout=self.timeout_seconds,
        )

        if response.status_code >= 400:
            raise OllamaClientError(self._error_message(response))

        data = response.json()
        try:
            text = data["message"]["content"].strip()
        except (KeyError, TypeError, AttributeError) as error:
            raise OllamaClientError("Ollama returned an unexpected response.") from error

        if not text:
            raise OllamaClientError("Ollama returned an empty response.")
        return text

    def _chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
    ) -> Iterator[str]:
        with httpx.stream(
            "POST",
            f"{self.base_url.rstrip('/')}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": True,
                "keep_alive": self.keep_alive,
                "options": {
                    "temperature": temperature,
                    "num_predict": self.num_predict,
                },
            },
            timeout=self.timeout_seconds,
        ) as response:
            if response.status_code >= 400:
                response.read()
                raise OllamaClientError(self._error_message(response))

            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError as error:
                    raise OllamaClientError(
                        "Ollama returned an unexpected stream response."
                    ) from error

                if data.get("done"):
                    break

                content = data.get("message", {}).get("content")
                if isinstance(content, str) and content:
                    yield content

    @staticmethod
    def _messages_for_ollama(messages: list[Message]) -> list[dict[str, str]]:
        return [
            {
                "role": "assistant" if message.role == "assistant" else "user",
                "content": message.content,
            }
            for message in messages
        ]

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"Ollama request failed with status {response.status_code}."

        detail = payload.get("error")
        if isinstance(detail, str) and detail:
            return detail
        return f"Ollama request failed with status {response.status_code}."

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are ChatbotTutorAI, a helpful tutor. "
            "Answer clearly, adapt to the student's level, "
            "and ask a short follow-up question when useful."
        )
