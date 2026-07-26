"""Google Gemini text generation client."""

from dataclasses import dataclass

import httpx

from backend.models.chat import Message


class GeminiClientError(RuntimeError):
    """Raised when Gemini cannot produce a usable response."""


@dataclass(frozen=True)
class GeminiClient:
    """Minimal Gemini REST client for chat-style text responses."""

    api_key: str
    model: str
    timeout_seconds: float = 30.0

    def generate_reply(self, messages: list[Message]) -> str:
        response = httpx.post(
            self._generate_content_url(),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            json={
                "contents": self._contents_from_messages(messages),
                "systemInstruction": {
                    "parts": [
                        {
                            "text": (
                                "You are ChatbotTutorAI, a helpful tutor. "
                                "Answer clearly, adapt to the student's level, "
                                "and ask a short follow-up question when useful."
                            )
                        }
                    ]
                },
            },
            timeout=self.timeout_seconds,
        )

        if response.status_code >= 400:
            raise GeminiClientError(self._error_message(response))

        data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts).strip()
        except (KeyError, IndexError, TypeError) as error:
            raise GeminiClientError("Gemini returned an unexpected response.") from error

        if not text:
            raise GeminiClientError("Gemini returned an empty response.")
        return text

    def _generate_content_url(self) -> str:
        return (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.model}:generateContent"
        )

    @staticmethod
    def _contents_from_messages(messages: list[Message]) -> list[dict[str, object]]:
        contents: list[dict[str, object]] = []
        for message in messages:
            role = "model" if message.role == "assistant" else "user"
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": message.content}],
                }
            )
        return contents

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"Gemini request failed with status {response.status_code}."

        detail = payload.get("error", {}).get("message")
        if isinstance(detail, str) and detail:
            return detail
        return f"Gemini request failed with status {response.status_code}."
