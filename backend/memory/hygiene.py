"""Shared rules for keeping memory focused on useful learning context."""

from __future__ import annotations

import re


_FILLER_WORDS = {
    "a",
    "abt",
    "about",
    "are",
    "bro",
    "dude",
    "hi",
    "hello",
    "hey",
    "k",
    "man",
    "me",
    "ok",
    "okay",
    "sup",
    "thanks",
    "thank",
    "thx",
    "ty",
    "u",
    "what",
    "wsp",
    "yo",
    "you",
}

_TECHNICAL_KEYWORDS = {
    "algorithm",
    "api",
    "bangalore",
    "biology",
    "bio",
    "cell",
    "chromadb",
    "classifies",
    "classificaiton",
    "classification",
    "code",
    "coding",
    "dna",
    "enzyme",
    "edges",
    "fastapi",
    "genetics",
    "gate",
    "hybrid",
    "implementation",
    "iisc",
    "java",
    "langgraph",
    "linked",
    "lists",
    "live",
    "lives",
    "matrix",
    "memory",
    "mitosis",
    "molecule",
    "multiplication",
    "nodes",
    "nlp",
    "photosynthesis",
    "programming",
    "python",
    "protein",
    "rag",
    "stategraph",
    "text",
}

_LEARNING_PATTERNS = (
    re.compile(
        r"\b(?:explain|teach|learn|learned|mastered|completed|preparing|dream|live|lives|prefer|"
        r"study|understand|implement|build|code|debug|solve|"
        r"revise|practice|what is|what'?s|whats|where is|is it in|how does|how do|"
        r"why does|capital|correct yourself)\b",
        re.I,
    ),
)

_MEMORY_CONTROL_PATTERNS = (
    re.compile(
        r"\b(?:remember|memory|first conversation|first time|first chat|first message|"
        r"what did we discuss|what we discussed|summary|summarize|recap|what did we talk|what have we covered|"
        r"do u remember|do you remember)\b",
        re.I,
    ),
)

_SOCIAL_OR_CONTROL_ONLY_PATTERNS = (
    re.compile(
        r"^(?:nice|cool|wow|continue|go on|next|so whats next|what'?s next|"
        r"lets shift to a new conversation|let'?s shift to a new conversation|"
        r"thanks?|thank you|ty|thx)(?:\s+.*)?$",
        re.I,
    ),
)


def is_memory_control_request(text: str) -> bool:
    """Return true for requests about memory itself, not learner facts."""

    return _matches_any(text, _MEMORY_CONTROL_PATTERNS)


def is_low_signal_text(text: str) -> bool:
    """Return true for greetings, filler, punctuation, and social fragments."""

    normalized = _normalize(text)
    if not normalized:
        return True

    tokens = normalized.split()
    if len(tokens) <= 4 and all(token in _FILLER_WORDS for token in tokens):
        return True

    if len(tokens) <= 2 and not is_essential_learning_text(text):
        return True

    return False


def is_essential_learning_text(text: str) -> bool:
    """Return true when a user turn has durable learning or technical content."""

    normalized = _normalize(text)
    if not normalized or is_memory_control_request(text):
        return False

    tokens = set(normalized.split())
    if tokens & _TECHNICAL_KEYWORDS:
        return True
    if _matches_any(text, _LEARNING_PATTERNS) and len(normalized.split()) >= 2:
        return True

    return False


def is_polluted_memory_text(text: str) -> bool:
    """Return true for old stored memories created from control or filler turns."""

    normalized = _strip_memory_prefixes(text)
    has_learning_prefix = _has_legacy_learning_prefix(text)
    if re.search(r"^\s*tutor taught or reinforced\b", text, re.I):
        return True
    if normalized == "user thanked the tutor":
        return True
    if is_memory_control_request(normalized):
        return True
    if is_low_signal_text(normalized):
        return True
    if has_learning_prefix and not is_essential_learning_text(normalized):
        return True
    return _matches_any(normalized, _SOCIAL_OR_CONTROL_ONLY_PATTERNS)


def _normalize(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9.+# ]+", " ", text.lower())
    return " ".join(cleaned.split())


def _strip_memory_prefixes(text: str) -> str:
    normalized = text.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized).removesuffix(".").strip()
    for pattern in (
        r"^(?:student|user) is learning\s+",
        r"^tutor taught or reinforced\s+",
        r"^student goal:\s+",
        r"^learning preference:\s+",
        r"^study plan:\s+",
        r"^completed topic:\s+",
        r"^strong topic:\s+student understood\s+",
        r"^weak topic or misconception:\s+",
    ):
        normalized = re.sub(pattern, "", normalized, flags=re.I).strip()
    return normalized


def _has_legacy_learning_prefix(text: str) -> bool:
    return bool(
        re.search(
            r"^\s*(?:(?:student|user) is learning|tutor taught or reinforced)\b",
            text,
            re.I,
        )
    )


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)
