"""Intent extraction for tutor turns."""

import re

from backend.models.learner import IntentSignal


class IntentAgent:
    """Convert a raw user message into a compact learning intent."""

    prompt = (
        "Extract the user's learning intent as JSON with action, topic, "
        "raw_text, and confidence. Do not answer the user."
    )

    _topic_patterns = (
        re.compile(r"\b(?:learn(?:ing)?|study(?:ing)?|teach me|explain|understand)\s+(.+)", re.I),
        re.compile(r"\babout\s+(.+)", re.I),
    )

    def analyze(self, content: str) -> IntentSignal:
        text = content.strip()
        lowered = text.lower()
        action = "continue_learning"

        if any(word in lowered for word in ("explain", "what is", "teach me")):
            action = "learn_topic"
        elif any(word in lowered for word in ("build", "implement", "code", "create")):
            action = "build"
        elif any(word in lowered for word in ("confused", "stuck", "error", "mistake")):
            action = "debug_understanding"

        topic = self._topic_from_text(text)
        return IntentSignal(action=action, topic=topic, raw_text=text, confidence=0.75)

    def _topic_from_text(self, text: str) -> str | None:
        for pattern in self._topic_patterns:
            match = pattern.search(text)
            if match:
                return self._clean_topic(match.group(1))
        return self._clean_topic(text) if len(text.split()) <= 5 else None

    @staticmethod
    def _clean_topic(topic: str) -> str:
        cleaned = re.sub(r"[?.!]+$", "", topic.strip())
        return " ".join(cleaned.split())
