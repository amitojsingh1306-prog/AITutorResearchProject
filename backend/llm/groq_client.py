"""Groq chat completion client."""

from dataclasses import dataclass

import httpx

from backend.models.chat import Message


class GroqClientError(RuntimeError):
    """Raised when Groq cannot produce a usable response."""


@dataclass(frozen=True)
class GroqClient:
    """Minimal Groq REST client using the OpenAI-compatible API."""

    api_key: str
    model: str
    timeout_seconds: float = 30.0

    def generate_reply(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> str:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt or self._default_system_prompt(),
                    },
                    *self._messages_for_groq(messages),
                ],
                "temperature": 0.7,
            },
            timeout=self.timeout_seconds,
        )

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
