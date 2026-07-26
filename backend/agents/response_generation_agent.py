"""Final response generation prompt construction."""

from backend.models.chat import Message
from backend.models.learner import OrchestratedContext


class ResponseGenerationAgent:
    """Generate only the final user-facing response."""

    prompt = (
        "Write the final tutor response using conversation state, retrieved "
        "memories, reflection, teaching plan, and knowledge. Do not retrieve "
        "memory or change the plan."
    )

    def system_prompt(self, context: OrchestratedContext) -> str:
        memories = [
            (
                f"- {item.record.memory} "
                f"(score={item.total_score}, importance={item.record.importance}, "
                f"type={item.record.type})"
            )
            for item in context.memory.retrieved_memories[:6]
        ]
        reflections = [f"- {item.memory}" for item in context.reflection.insights]

        return "\n".join(
            [
                "You are ChatbotTutorAI, a persistent human-like AI tutor.",
                "Your response should emerge from memory, reflection, planning, and dialogue.",
                "Avoid robotic repetition. Do not start every answer with 'Since you already learned'.",
                "Only mention prior knowledge when it genuinely helps the current explanation.",
                "Dialogue Manager controls HOW you speak. Follow it over the planner for tone and length.",
                "",
                "Conversation state JSON:",
                context.conversation_state.model_dump_json(),
                "",
                "Intent JSON:",
                context.intent.model_dump_json(),
                "",
                "Knowledge JSON:",
                context.knowledge.model_dump_json(),
                "",
                "Teaching plan JSON:",
                context.plan.model_dump_json(),
                "",
                "Dialogue manager JSON:",
                context.dialogue.model_dump_json(),
                "",
                "Retrieved memories:",
                *(memories or ["- No relevant memories retrieved."]),
                "",
                "Reflection:",
                *(reflections or ["- No new reflection this turn."]),
                "",
                "Rules:",
                "- If dialogue length is short, reply in 1-2 short sentences.",
                "- If stop_after_acknowledgement is true, acknowledge and stop.",
                "- Do not add headings, bullets, summaries, or motivational outros for gratitude, greeting, goodbye, excitement, casual_chat, correction, or disagreement.",
                "- For gratitude, goodbye, excitement, and casual_chat, do not continue the lesson unless the user explicitly asks.",
                "- Avoid these openings: " + ", ".join(context.dialogue.avoid_openings),
                "- Never claim unsupported facts about the learner.",
                "- If the learner is confused, slow down and repair prerequisites.",
                "- If the learner shows understanding, move toward application.",
                "- If the learner switches topics, acknowledge it and start the new path.",
                "- Keep the answer beginner-friendly and practical.",
                "- End with a natural next step.",
            ]
        )

    def fallback_reply(self, context: OrchestratedContext) -> str:
        topic = context.knowledge.topic
        plan = context.plan
        dialogue = context.dialogue
        memories = [item.record.memory for item in context.memory.retrieved_memories[:3]]

        if dialogue.conversation_type == "gratitude":
            return "Happy to help. Glad it clicked."
        if dialogue.conversation_type == "goodbye":
            return "See you next time."
        if dialogue.conversation_type == "greeting":
            return "Hey! What would you like to work on today?"
        if dialogue.conversation_type == "excitement":
            return "I know, right? That part is genuinely cool."
        if dialogue.conversation_type == "casual_chat":
            return "I'm doing well. What would you like to work on?"
        if dialogue.conversation_type == "correction":
            return "Good catch. What should I adjust?"
        if dialogue.conversation_type == "disagreement":
            return "Fair point. Which part feels off?"
        if dialogue.conversation_type == "confusion":
            return "No worries. Which part is confusing?"
        if dialogue.conversation_type == "understanding":
            return "Nice. That means we can build on this now."

        if plan.mode == "review":
            return (
                f"No worries. Let's pause and rebuild {topic} from the point that feels unclear. "
                "We'll use a smaller example first, then continue once it clicks."
            )
        if plan.mode == "apply":
            return (
                f"Nice, that means you're ready to apply {topic}. "
                "Let's turn the idea into a tiny implementation next."
            )
        if plan.mode == "switch_topic":
            return (
                f"Got it, we'll save your current progress and switch to {topic}. "
                "I'll start from your current level and keep it practical."
            )
        if memories:
            prerequisites = context.knowledge.prerequisites
            if prerequisites:
                return (
                    f"Great progress. {context.knowledge.topic} is the next useful step "
                    f"after {', '.join(prerequisites)}. Let's connect those ideas with "
                    "a small practical example."
                )
            return (
                f"Great progress. The next step is {topic}. "
                f"I'll build from this context: {memories[0]}"
            )
        return (
            f"Let's work on {topic}. I'll keep this lesson connected to your progress "
            "so future explanations do not restart from scratch."
        )

    def select_messages(self, messages: list[Message]) -> list[Message]:
        return messages[-10:]
