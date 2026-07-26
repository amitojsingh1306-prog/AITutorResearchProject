"""Dialogue calibration between planning and final response generation."""

from backend.models.learner import (
    ConversationStateSignal,
    DialogueSignal,
    IntentSignal,
    TeachingPlan,
)


class DialogueManagerAgent:
    """Decide how the tutor should communicate, not what it should teach."""

    prompt = (
        "Given the user turn and teaching plan, return JSON dialogue controls: "
        "conversation_type, tone, length, style, acknowledgement, follow-up policy, "
        "and repetition constraints."
    )

    _avoid_openings = [
        "Since you've already learned",
        "Now that you've learned",
        "As we've discussed",
        "Keep Exploring, Stay Curious",
        "Great progress.",
        "It was my pleasure",
    ]

    def calibrate(
        self,
        *,
        intent: IntentSignal,
        conversation_state: ConversationStateSignal,
        plan: TeachingPlan,
    ) -> DialogueSignal:
        conversation_type = self._conversation_type(intent, conversation_state)
        tone = "calm and encouraging"
        length = "medium"
        style = "mentor-like, practical, natural"
        acknowledgement = ""
        ask_follow_up = True
        stop_after_acknowledgement = False
        rules = [
            "Avoid exaggerated praise.",
            "Avoid motivational speeches.",
            "Avoid headings for short social replies.",
            "Match the user's energy.",
        ]

        if conversation_type == "gratitude":
            tone = "warm and brief"
            length = "short"
            acknowledgement = "You're welcome."
            ask_follow_up = False
            stop_after_acknowledgement = True
            rules.extend(
                [
                    "Reply in one short sentence, or two short sentences at most.",
                    "Do not summarize previous lessons.",
                    "Do not suggest a long list of next steps.",
                ]
            )
        elif conversation_type == "understanding":
            tone = "briefly encouraging"
            length = "short"
            acknowledgement = "Nice."
            ask_follow_up = False
            stop_after_acknowledgement = False
            rules.append("Move toward application without repeating prior-memory phrasing.")
        elif conversation_type == "confusion":
            tone = "reassuring"
            length = "short"
            acknowledgement = "No worries."
            ask_follow_up = True
            stop_after_acknowledgement = False
            rules.append("Ask what part is confusing instead of continuing the lesson.")
        elif conversation_type == "excitement":
            tone = "light and engaged"
            length = "short"
            acknowledgement = "I know, right?"
            ask_follow_up = False
            rules.append("Respond casually; do not launch a full lesson.")
        elif conversation_type == "goodbye":
            tone = "warm and concise"
            length = "short"
            acknowledgement = "See you next time."
            ask_follow_up = False
            stop_after_acknowledgement = True
            rules.append("Do not add a motivational outro.")
        elif conversation_type == "greeting":
            tone = "friendly and simple"
            length = "short"
            acknowledgement = "Hey."
            ask_follow_up = True
            rules.append("Ask what the learner wants to work on without teaching yet.")
        elif conversation_type == "casual_chat":
            tone = "natural and light"
            length = "short"
            acknowledgement = ""
            ask_follow_up = False
            stop_after_acknowledgement = True
            rules.append("Keep casual chat brief and human; do not turn it into a lesson.")
        elif conversation_type == "correction":
            tone = "humble and direct"
            length = "short"
            acknowledgement = "Good catch."
            ask_follow_up = True
            rules.append("Acknowledge the correction and adjust without defensiveness.")
        elif conversation_type == "disagreement":
            tone = "curious and respectful"
            length = "short"
            acknowledgement = "Fair point."
            ask_follow_up = True
            rules.append("Do not argue; invite the specific concern or re-check the claim.")
        elif conversation_type == "progression":
            length = "medium"
            acknowledgement = "Let's continue."
            rules.append("Continue directly without summarizing the whole conversation.")
        elif conversation_type == "topic_switch":
            tone = "flexible and direct"
            length = "medium"
            acknowledgement = "Got it."
            ask_follow_up = False
            rules.append("Acknowledge the switch once, then start the new topic.")
        elif conversation_type == "question":
            length = "detailed" if plan.depth != "beginner" else "medium"
            acknowledgement = "Good question."

        return DialogueSignal(
            conversation_type=conversation_type,
            tone=tone,
            length=length,
            style=style,
            acknowledgement=acknowledgement,
            ask_follow_up=ask_follow_up,
            stop_after_acknowledgement=stop_after_acknowledgement,
            avoid_openings=self._avoid_openings,
            response_rules=rules,
        )

    def _conversation_type(
        self,
        intent: IntentSignal,
        conversation_state: ConversationStateSignal,
    ) -> str:
        state = conversation_state.state
        if state == "gratitude":
            return "gratitude"
        if state == "understanding":
            return "understanding"
        if state == "confused":
            return "confusion"
        if state == "excitement":
            return "excitement"
        if state == "greeting":
            return "greeting"
        if state == "casual_chat":
            return "casual_chat"
        if state == "correction":
            return "correction"
        if state == "disagreement":
            return "disagreement"
        if state == "conversation_end":
            return "goodbye"
        if state == "topic_switch":
            return "topic_switch"
        if state == "progression":
            return "progression"
        if intent.action == "learn_topic":
            return "question"
        return "follow_up"
