"""Teaching plan generation from diffused context."""

from backend.models.learner import (
    ConversationStateSignal,
    KnowledgeSignal,
    MemorySignal,
    ReflectionSignal,
    TeachingPlan,
)


class TeachingPlannerAgent:
    """Decide what to teach and how, without writing the final response."""

    prompt = (
        "Create a JSON teaching plan with mode, review, depth, steps, "
        "next_action, and tone. Never answer the user directly."
    )

    def plan(
        self,
        *,
        conversation_state: ConversationStateSignal,
        memory: MemorySignal,
        knowledge: KnowledgeSignal,
        reflection: ReflectionSignal,
    ) -> TeachingPlan:
        state = conversation_state.state
        mode = "continue"
        review = False
        depth = "beginner"
        tone = "encouraging"

        if state == "confused":
            mode = "review"
            review = True
            tone = "reassuring"
        elif state == "topic_switch":
            mode = "switch_topic"
            tone = "flexible"
        elif state == "skip":
            mode = "skip"
            tone = "direct"
        elif state == "understanding":
            mode = "apply"
            tone = "celebratory"
        elif state == "progression":
            mode = "progress"
        elif state in {
            "gratitude",
            "greeting",
            "conversation_end",
            "excitement",
            "casual_chat",
            "correction",
            "disagreement",
        }:
            mode = "acknowledge"
            tone = "warm"

        style = memory.profile.preferred_explanation_style or ""
        if "hands-on" in style:
            depth = "implementation-first"

        steps = self._steps_for_mode(mode, knowledge)
        if reflection.insights:
            steps.append("Use the latest reflection to adapt the teaching style.")

        return TeachingPlan(
            mode=mode,
            review=review,
            depth=depth,
            steps=steps,
            next_action=self._next_action(mode),
            tone=tone,
        )

    def _steps_for_mode(self, mode: str, knowledge: KnowledgeSignal) -> list[str]:
        topic = knowledge.topic
        if mode == "review":
            return [
                "Pause progression.",
                "Identify the prerequisite causing confusion.",
                f"Re-explain {topic} using a smaller example.",
                "Ask the learner to confirm the repaired concept.",
            ]
        if mode == "switch_topic":
            return [
                "Acknowledge the topic switch.",
                "Save current progress.",
                f"Start {topic} from the learner's current level.",
            ]
        if mode == "skip":
            return [
                "Mark the topic as skipped.",
                "Move to the next useful concept.",
            ]
        if mode == "acknowledge":
            return [
                "Acknowledge the learner naturally.",
                "Do not continue teaching unless the user asks.",
            ]
        if mode == "apply":
            return [
                "Congratulate the learner briefly.",
                f"Move from understanding {topic} to applying it.",
                "Give a small implementation challenge.",
            ]
        return [
            "Briefly connect to relevant prior memory if useful.",
            f"Introduce {topic}.",
            "Explain the core idea.",
            "Show a small practical example.",
            "End with a next step.",
        ]

    @staticmethod
    def _next_action(mode: str) -> str:
        if mode == "review":
            return "ask_check_understanding"
        if mode == "apply":
            return "assign_practice"
        if mode == "switch_topic":
            return "start_new_path"
        if mode == "acknowledge":
            return "stop"
        return "continue_learning"
