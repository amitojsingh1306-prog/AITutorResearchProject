"""Importance scoring for MemGPT-inspired long-term memory promotion.

MemGPT separates short-lived context from external memory and decides when a
piece of information is worth writing out of the active context window. This
module implements that decision as a small, inspectable heuristic rather than a
full learned memory controller. Keeping it isolated makes benchmarking easy:
future experiments can replace this scorer without changing the chatbot flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.memory.hygiene import (
    is_essential_learning_text,
    is_low_signal_text,
    is_memory_control_request,
)
from backend.models.learner import ConversationStateSignal


@dataclass(frozen=True)
class ImportanceDecision:
    """Result of deciding whether a user turn deserves persistent memory."""

    importance: int
    memory_type: str
    status: str
    should_promote: bool
    reason: str


class ImportanceScorer:
    """Heuristic promotion policy for educational long-term memory.

    The goal is deliberately narrower than original MemGPT: we only promote
    stable learner information such as goals, misconceptions, weak topics,
    strong topics, completed topics, learning preferences, achievements, and
    study plans. Greetings and temporary small talk remain in working memory
    and naturally fall out of the limited context window.
    """

    promotion_threshold = 6
    ignored_states = {
        "gratitude",
        "greeting",
        "conversation_end",
        "casual_chat",
    }

    _goal_patterns = (
        re.compile(
            r"\b(?:my goal is|goal|want to become|want to learn|i want to master)\b",
            re.I,
        ),
    )
    _preference_patterns = (
        re.compile(
            r"\b(?:i prefer|i like|i learn best|show me examples|hands-on|implementation)\b",
            re.I,
        ),
    )
    _achievement_patterns = (
        re.compile(r"\b(?:i built|i implemented|i completed|i finished|i solved)\b", re.I),
    )
    _study_plan_patterns = (
        re.compile(r"\b(?:study plan|schedule|practice plan|revision plan|roadmap)\b", re.I),
    )
    _strong_topic_patterns = (
        re.compile(
            r"\b(?:i understand|i get|got it|i know|strong at|good at|comfortable with)\b",
            re.I,
        ),
    )
    _weak_topic_patterns = (
        re.compile(
            r"\b(?:confused|stuck|weak at|struggle|don't understand|do not understand|mistake)\b",
            re.I,
        ),
    )
    def score(
        self,
        *,
        content: str,
        conversation_state: ConversationStateSignal,
    ) -> ImportanceDecision:
        text = content.strip()
        lowered = text.lower()

        if conversation_state.state in self.ignored_states:
            return ImportanceDecision(
                importance=1,
                memory_type="ignored",
                status="working_only",
                should_promote=False,
                reason="Social or casual turns should not be promoted to long-term memory.",
            )
        if is_low_signal_text(text):
            return ImportanceDecision(
                importance=1,
                memory_type="ignored",
                status="working_only",
                should_promote=False,
                reason="Casual-only turns belong in working memory, not permanent memory.",
            )
        if is_memory_control_request(text):
            return ImportanceDecision(
                importance=1,
                memory_type="ignored",
                status="working_only",
                should_promote=False,
                reason="Memory lookup questions are control requests, not learner facts.",
            )

        if self._matches_any(text, self._goal_patterns):
            return self._promote(10, "goal", "active", "The learner stated a durable goal.")
        if self._matches_any(text, self._study_plan_patterns):
            return self._promote(
                9,
                "study_plan",
                "active",
                "The learner mentioned a study plan.",
            )
        if self._matches_any(text, self._preference_patterns):
            return self._promote(
                8,
                "preference",
                "active",
                "The learner stated a learning preference.",
            )
        if self._matches_any(text, self._achievement_patterns):
            return self._promote(
                9,
                "achievement",
                "completed",
                "The learner reported an achievement.",
            )
        if conversation_state.state == "confused" or self._matches_any(
            text,
            self._weak_topic_patterns,
        ):
            return self._promote(
                8,
                "weak_topic",
                "needs_review",
                "The learner signaled confusion or a weak topic.",
            )
        if conversation_state.state == "understanding" or self._matches_any(
            text,
            self._strong_topic_patterns,
        ):
            return self._promote(
                8,
                "strong_topic",
                "completed",
                "The learner signaled understanding.",
            )
        if "completed" in lowered or "learned" in lowered:
            return self._promote(
                7,
                "completed_topic",
                "completed",
                "The learner reported completed learning.",
            )
        if conversation_state.state in {
            "learning",
            "continuation",
            "progression",
            "topic_switch",
        } and is_essential_learning_text(text):
            return self._promote(
                6,
                "learning_event",
                "active",
                "The turn describes an active learning topic.",
            )

        return ImportanceDecision(
            importance=3,
            memory_type="ignored",
            status="working_only",
            should_promote=False,
            reason="The turn does not contain stable learner information.",
        )

    def _promote(
        self,
        importance: int,
        memory_type: str,
        status: str,
        reason: str,
    ) -> ImportanceDecision:
        return ImportanceDecision(
            importance=importance,
            memory_type=memory_type,
            status=status,
            should_promote=importance >= self.promotion_threshold,
            reason=reason,
        )

    @staticmethod
    def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
        return any(pattern.search(text) for pattern in patterns)
