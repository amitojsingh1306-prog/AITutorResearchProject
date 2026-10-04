"""Small local RAG retriever for core tutoring topics.

The project already has long-term learner memory in ChromaDB. This module is a
separate knowledge layer: it retrieves compact educational facts for the current
topic so the tutor can ground answers without relying only on the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RagChunk:
    id: str
    topic: str
    text: str
    keywords: tuple[str, ...]


class LocalRagRetriever:
    """Keyword retriever over a compact built-in CS knowledge base."""

    def __init__(self, chunks: tuple[RagChunk, ...] | None = None) -> None:
        self._chunks = chunks or DEFAULT_CHUNKS

    def retrieve(self, query: str, *, limit: int = 3) -> list[RagChunk]:
        query_terms = self._terms(query)
        if not query_terms:
            return []

        scored: list[tuple[int, RagChunk]] = []
        for chunk in self._chunks:
            chunk_terms = set(chunk.keywords) | self._terms(chunk.topic) | self._terms(chunk.text)
            score = len(query_terms & chunk_terms)
            if score > 0:
                scored.append((score, chunk))

        return [
            chunk
            for _, chunk in sorted(
                scored,
                key=lambda item: (item[0], item[1].topic),
                reverse=True,
            )[:limit]
        ]

    @staticmethod
    def _terms(text: str) -> set[str]:
        return {
            token
            for token in re.sub(r"[^a-z0-9+#. ]+", " ", text.lower()).split()
            if len(token) > 1
            and token
            not in {
                "a",
                "an",
                "and",
                "are",
                "for",
                "in",
                "is",
                "me",
                "of",
                "the",
                "to",
                "what",
            }
        }


DEFAULT_CHUNKS: tuple[RagChunk, ...] = (
    RagChunk(
        id="recursion-core",
        topic="Recursion",
        keywords=("recursion", "recursive", "base", "case", "call", "stack"),
        text=(
            "Recursion is a technique where a function solves a problem by calling "
            "itself on a smaller input. A correct recursive solution needs a base "
            "case that stops the calls and a recursive case that reduces the problem."
        ),
    ),
    RagChunk(
        id="recursion-example",
        topic="Recursion",
        keywords=("recursion", "factorial", "example", "dry", "run"),
        text=(
            "A factorial example is factorial(n) = n * factorial(n - 1), with "
            "factorial(1) = 1 as the base case. Each call waits on the next smaller call."
        ),
    ),
    RagChunk(
        id="linked-list-core",
        topic="Linked Lists",
        keywords=("linked", "list", "node", "pointer", "next"),
        text=(
            "A linked list stores data in nodes. Each node contains a value and a "
            "reference to the next node, so insertions can be efficient when the "
            "target position is already known."
        ),
    ),
    RagChunk(
        id="binary-search-core",
        topic="Binary Search",
        keywords=("binary", "search", "sorted", "mid", "log"),
        text=(
            "Binary search works on sorted data by checking the middle element and "
            "discarding half of the search space each step. Its time complexity is O(log n)."
        ),
    ),
    RagChunk(
        id="gate-cse-core",
        topic="GATE CSE",
        keywords=("gate", "cse", "exam", "preparation", "computer", "science"),
        text=(
            "GATE CSE preparation should prioritize core subjects such as data "
            "structures, algorithms, operating systems, DBMS, computer networks, "
            "digital logic, theory of computation, and aptitude."
        ),
    ),
)
