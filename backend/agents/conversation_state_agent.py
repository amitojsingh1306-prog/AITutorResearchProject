"""Conversation state classification for tutor turns."""

import re

from backend.models.learner import ConversationStateSignal, IntentSignal


class ConversationStateAgent:
    """Classify the user's message so downstream agents can react appropriately."""

    prompt = (
        "Classify the user turn as learning, continuation, understanding, "
        "confused, gratitude, excitement, greeting, progression, correction, "
        "disagreement, casual_chat, topic_switch, skip, or conversation_end. "
        "Return JSON only."
    )

    _gratitude_patterns = (
        re.compile(r"\b(?:thanks?|thank you|ty|thx)\b", re.I),
    )
    _excitement_patterns = (
        re.compile(r"\b(?:wow|awesome|cool|neat|interesting|love that)\b", re.I),
    )
    _greeting_patterns = (
        re.compile(r"^(?:hello|hi|hey|yo|good morning|good afternoon|good evening)[!. ]*$", re.I),
    )
    _understanding_patterns = (
        re.compile(r"\b(?:i understand|i get it|got it|makes sense|that makes sense|it clicked)\b", re.I),
    )
    _confusion_patterns = (
        re.compile(r"\b(?:confused|don't understand|do not understand|stuck|lost|unclear)\b", re.I),
    )
    _progression_patterns = (
        re.compile(r"^(?:what'?s next|next|continue|go on|keep going|ready for the next topic)[?.! ]*$", re.I),
    )
    _topic_switch_patterns = (
        re.compile(r"\b(?:actually|instead|now i want|switch to|change topic)\b", re.I),
    )
    _correction_patterns = (
        re.compile(r"\b(?:not quite|that's not right|that is not right|i meant|correction)\b", re.I),
    )
    _disagreement_patterns = (
        re.compile(r"\b(?:i disagree|disagree|i don't think so|that seems wrong|are you sure)\b", re.I),
    )
    _goodbye_patterns = (
        re.compile(r"^(?:bye|goodbye|see you|see ya|that'?s all|talk later)[!. ]*$", re.I),
    )
    _casual_chat_patterns = (
        re.compile(r"\b(?:how are you|what's up|whats up|lol|haha)\b", re.I),
    )

    def classify(self, intent: IntentSignal) -> ConversationStateSignal:
        text = intent.raw_text.strip()
        state = "learning"
        reaction_type = "normal"
        reason = "The learner is asking for instruction."

        if self._matches_any(text, self._gratitude_patterns):
            state = "gratitude"
            reason = "The learner is thanking the tutor."
        elif self._matches_any(text, self._understanding_patterns):
            state = "understanding"
            reason = "The learner is signaling comprehension."
        elif self._matches_any(text, self._confusion_patterns):
            state = "confused"
            reaction_type = "unexpected"
            reason = "The learner needs review or prerequisite repair."
        elif self._matches_any(text, self._goodbye_patterns):
            state = "conversation_end"
            reason = "The learner is closing the conversation."
        elif self._matches_any(text, self._greeting_patterns):
            state = "greeting"
            reason = "The learner is greeting the tutor."
        elif self._matches_any(text, self._progression_patterns):
            state = "progression"
            reason = "The learner wants the next step."
        elif self._matches_any(text, self._correction_patterns):
            state = "correction"
            reaction_type = "unexpected"
            reason = "The learner is correcting the tutor or clarifying intent."
        elif self._matches_any(text, self._disagreement_patterns):
            state = "disagreement"
            reaction_type = "unexpected"
            reason = "The learner disagrees or wants the tutor to re-check."
        elif self._matches_any(text, self._excitement_patterns) and intent.action != "learn_topic":
            state = "excitement"
            reason = "The learner is expressing excitement."
        elif self._matches_any(text, self._topic_switch_patterns):
            state = "topic_switch"
            reaction_type = "unexpected"
            reason = "The learner is changing the learning path."
        elif self._matches_any(text, self._casual_chat_patterns):
            state = "casual_chat"
            reason = "The learner is making a casual conversational turn."
        elif re.search(r"\bskip\b", text, re.I):
            state = "skip"
            reaction_type = "unexpected"
            reason = "The learner wants to skip the current topic."
        elif intent.topic:
            state = "continuation" if intent.action == "learn_topic" else "learning"

        return ConversationStateSignal(
            state=state,
            reaction_type=reaction_type,
            reason=reason,
        )

    @staticmethod
    def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
        return any(pattern.search(text) for pattern in patterns)
