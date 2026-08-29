"""Groq chat client for hosted Llama models."""

from collections.abc import Iterator
from dataclasses import dataclass
import json

import httpx

from backend.models.chat import Message


class GroqClientError(RuntimeError):
    """Raised when Groq cannot produce a usable response."""


@dataclass(frozen=True)
class GroqClient:
    """Minimal Groq REST client with the app's existing LLM interface."""

    api_key: str
    model: str = "llama-3.3-70b-versatile"
    base_url: str = "https://api.groq.com/openai/v1"
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
                *self._messages_for_groq(messages),
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
                *self._messages_for_groq(messages),
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
        try:
            response = httpx.post(
                self._chat_url(),
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "temperature": temperature,
                    "max_tokens": self.num_predict,
                },
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as error:
            raise GroqClientError(f"Groq request failed: {error}") from error

        if response.status_code >= 400:
            raise GroqClientError(self._error_message(response))

        data = response.json()
        try:
            text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise GroqClientError("Groq returned an unexpected response.") from error

        if not text:
            raise GroqClientError("Groq returned an empty response.")
        return text

    def _chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
    ) -> Iterator[str]:
        try:
            stream = httpx.stream(
                "POST",
                self._chat_url(),
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "temperature": temperature,
                    "max_tokens": self.num_predict,
                },
                timeout=self.timeout_seconds,
            )
            with stream as response:
                yield from self._iter_stream_response(response)
        except httpx.HTTPError as error:
            raise GroqClientError(f"Groq stream request failed: {error}") from error

    def _iter_stream_response(self, response: httpx.Response) -> Iterator[str]:
        if response.status_code >= 400:
            response.read()
            raise GroqClientError(self._error_message(response))

        for line in response.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            payload = line.removeprefix("data: ").strip()
            if payload == "[DONE]":
                break
            try:
                data = json.loads(payload)
            except json.JSONDecodeError as error:
                raise GroqClientError(
                    "Groq returned an unexpected stream response."
                ) from error

            content = data.get("choices", [{}])[0].get("delta", {}).get("content")
            if isinstance(content, str) and content:
                yield content

    def _chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _messages_for_groq(messages: list[Message]) -> list[dict[str, str]]:
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
            return f"Groq request failed with status {response.status_code}."

        detail = payload.get("error", {}).get("message")
        if isinstance(detail, str) and detail:
            return detail
        return f"Groq request failed with status {response.status_code}."

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are ChatbotTutorAI, a helpful tutor. "
            "Answer clearly, adapt to the student's level, "
            "and ask a short follow-up question when useful."
        )
