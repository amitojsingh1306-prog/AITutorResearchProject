"""Final response generation prompt construction."""

import json
import logging

from backend.models.chat import Message
from backend.models.learner import OrchestratedContext


logger = logging.getLogger(__name__)


class ResponseGenerationAgent:
    """Generate only the final user-facing response."""

    common_topic_outlines = {
        "dfs": [
            "Definition",
            "Working",
            "Example",
            "Time Complexity",
            "Applications",
        ],
        "depth first search": [
            "Definition",
            "Working",
            "Example",
            "Time Complexity",
            "Applications",
        ],
        "bfs": [
            "Definition",
            "Working",
            "Example",
            "Time Complexity",
            "Applications",
        ],
        "breadth first search": [
            "Definition",
            "Working",
            "Example",
            "Time Complexity",
            "Applications",
        ],
        "tcp/ip": [
            "Overview",
            "Layers",
            "Protocols",
            "Advantages",
            "Comparison with OSI",
        ],
        "tcp ip": [
            "Overview",
            "Layers",
            "Protocols",
            "Advantages",
            "Comparison with OSI",
        ],
        "normalization": [
            "Definition",
            "Need",
            "1NF",
            "2NF",
            "3NF",
            "BCNF",
        ],
        "recursion": [
            "Definition",
            "Base Case",
            "Example",
            "Call Stack",
            "Complexity",
        ],
        "linked list": [
            "Definition",
            "Structure",
            "Operations",
            "Time Complexity",
            "Applications",
        ],
    }

    max_prompt_messages = 4
    max_prompt_memories = 2
    max_reflection_items = 1
    max_memory_chars = 180
    max_reflection_chars = 160
    max_selected_headings = 3

    prompt = (
        "Write the final tutor response using conversation state, retrieved "
        "memories, reflection, teaching plan, and knowledge. Do not retrieve "
        "memory or change the plan."
    )

    outline_system_prompt = (
        "Return ONLY a JSON array of teaching section headings. "
        "No explanations. No markdown. No prose."
    )

    def system_prompt(
        self,
        context: OrchestratedContext,
        *,
        response_mode: str = "normal",
        structured_context: list[str] | None = None,
        explicit_memory_request: bool = False,
        selected_headings: list[str] | None = None,
        remaining_headings: list[str] | None = None,
        full_outline: list[str] | None = None,
    ) -> str:
        memories = self._hidden_memory_context(context)
        logger.warning(
            "[GENERATION DEBUG] Memory context injected: %s count=%s",
            "YES" if context.memory_context else "NO",
            len(context.memory_context),
        )
        for index, item in enumerate(context.memory_context, start=1):
            logger.warning(
                "[GENERATION DEBUG] Memory context %s type=%s topic=%s content=%s",
                index,
                item.type,
                item.topic or "",
                self._compact_text(item.content, self.max_memory_chars),
            )
        reflections = [
            f"- {self._compact_text(item.memory, self.max_reflection_chars)}"
            for item in context.reflection.insights[: self.max_reflection_items]
        ]
        full_outline = full_outline or []
        selected_headings = selected_headings or []
        remaining_headings = remaining_headings or []
        structured_context = structured_context or []

        return "\n".join(
            [
                "You are ChatbotTutorAI, a persistent human-like AI tutor.",
                "Your response should use hidden context for reasoning and personalization.",
                "Avoid robotic repetition. Do not start every answer with 'Since you already learned'.",
                "Do not mention prior memories unless the user explicitly asks about memory or conversation history.",
                "Dialogue Manager controls HOW you speak. Follow it over the planner for tone and length.",
                f"Response mode: {response_mode}",
                f"Explicit memory/history request: {explicit_memory_request}",
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
                "Hidden learner context from retrieved memories:",
                *(memories or ["- No relevant hidden learner context."]),
                "",
                "Hidden memory policy:",
                "- The message list contains only the active conversation buffer.",
                "- Older chat history is intentionally outside the context window.",
                "- Memory Retrieval Context contains the only retrieved memories grounded for this response.",
                "- Retrieved memories are hidden reasoning context, not response content.",
                "- Use hidden memories only to improve reasoning, personalization, continuity, and response quality.",
                "- Do not mention, summarize, quote, or list hidden memories unless Explicit memory/history request is true.",
                "",
                "Reflection:",
                *(reflections or ["- No new reflection this turn."]),
                "",
                "Structured retrieved context for the current request:",
                *(structured_context or ["- No special retrieved context."]),
                "",
                "Application-selected lesson outline:",
                *(self._numbered_lines(full_outline) or ["- No lesson headings for this turn."]),
                "",
                "Headings to explain now:",
                *(self._plain_lines(selected_headings) or ["- No lesson headings for this turn."]),
                "",
                "Headings reserved for later:",
                *(self._plain_lines(remaining_headings) or ["- None."]),
                "",
                "Rules:",
                "- Start answering immediately. Do not open with 'Sure', 'Let's understand', 'Let's explore', or similar introductions.",
                "- Mode-specific rules override all generic rules below.",
                *self._mode_rules(response_mode, bool(remaining_headings)),
                "- In lesson mode, keep the entire response under about 30 lines.",
                "- In lesson mode, each section must contain only 3-4 short lines.",
                "- Prefer bullets over long paragraphs.",
                "- Use at most one short example, only when it helps.",
                "- Treat 700 tokens as a maximum budget, not a target length.",
                "- For simple questions, answer concisely and stop early, roughly 200-320 tokens or less.",
                "- For complex educational questions, use only enough budget to complete the first 2-3 sections clearly.",
                "- Prefer a complete answer over an artificially short answer.",
                "- Do not truncate important explanations just to stay brief.",
                "- If nearing the output limit, finish the current section and stop naturally.",
                "- Never start a new section unless there is enough space to complete it.",
                "- Avoid repeating the same idea in different words.",
                "- Avoid filler, generic motivation, and unnecessary repetition.",
                "- Use structured retrieved context only when it directly answers an explicit memory/history request.",
                "- Do not expose raw internal labels like memory_history_request, status, instruction, topic, memory, or learning_turn.",
                "- Do not return retrieved memory entries verbatim unless the user explicitly asks for raw memory contents.",
                "- Do not invent previous conversations, topics, projects, preferences, or facts.",
                "- Only claim a past discussion or remembered user detail when it exists in Memory Retrieval Context or Structured retrieved context.",
                "- If the user asks about past memory/history and no grounded context exists, say you do not have enough saved context.",
                "- For explicit memory/history questions, summarize the grounded context naturally instead of dumping raw memory entries.",
                "- For ordinary teaching, coding, QA, or list requests, answer the user's actual question without announcing what you remember.",
                "- In lesson mode, never try to cover an entire textbook topic in one response.",
                "- In lesson mode, prefer multiple complete responses over one incomplete response.",
                "- After drafting, check that the answer is complete and has no unfinished sections; if not, shorten it instead of leaving a partial section.",
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
                "- In QA and lesson mode, end with a natural next step.",
            ]
        )

    def fallback_reply(self, context: OrchestratedContext) -> str:
        topic = context.knowledge.topic
        plan = context.plan
        dialogue = context.dialogue

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
        prerequisites = context.knowledge.prerequisites
        if prerequisites:
            return (
                f"{context.knowledge.topic} builds on {', '.join(prerequisites)}. "
                "Let's connect the ideas with a small practical example."
            )
        return (
            f"Let's work on {topic}. I'll keep it beginner-friendly and practical."
        )

    def select_messages(self, context: OrchestratedContext) -> list[Message]:
        return context.memory.working_messages[-self.max_prompt_messages :]

    def _hidden_memory_context(self, context: OrchestratedContext) -> list[str]:
        groups: dict[str, list[str]] = {
            "goals": [],
            "preferences": [],
            "progress": [],
            "learning_difficulties": [],
            "facts": [],
        }
        for item in context.memory_context[: self.max_prompt_memories]:
            section = self._memory_context_section(item.type)
            groups[section].append(
                self._compact_text(item.content, self.max_memory_chars)
            )

        lines: list[str] = []
        for section, values in groups.items():
            if not values:
                continue
            lines.append(f"{section}:")
            lines.extend(f"- {value}" for value in values)
        return lines

    @staticmethod
    def _memory_context_section(memory_type: str) -> str:
        return {
            "goal": "goals",
            "preference": "preferences",
            "knowledge_state": "progress",
            "achievement": "progress",
            "learning_difficulty": "learning_difficulties",
            "fact": "facts",
        }.get(memory_type, "facts")

    @staticmethod
    def _compact_text(text: str, max_chars: int) -> str:
        compact = " ".join(text.strip().split())
        if len(compact) <= max_chars:
            return compact
        return f"{compact[: max_chars - 1].rstrip()}…"

    def lesson_outline(self, context: OrchestratedContext, llm_client: object | None) -> list[str]:
        if context.dialogue.stop_after_acknowledgement:
            return []
        if context.dialogue.conversation_type in {
            "gratitude",
            "greeting",
            "goodbye",
            "excitement",
            "casual_chat",
            "correction",
            "disagreement",
        }:
            return []

        topic_key = self._normalize_topic(context.knowledge.topic)
        if topic_key in self.common_topic_outlines:
            return self.common_topic_outlines[topic_key]

        if llm_client is not None and hasattr(llm_client, "generate_text"):
            outline = self._generate_unknown_topic_outline(context, llm_client)
            if outline:
                return outline

        action = context.intent.action.lower()
        raw_text = context.intent.raw_text.lower()
        if any(word in raw_text for word in ("compare", "difference", "vs")):
            return ["Definition", "Key Differences", "Example", "When to Use"]
        if action in {"compare", "comparison"}:
            return ["Definition", "Key Differences", "Example", "When to Use"]
        if action in {"problem_solving", "solve", "practice", "debug_understanding"}:
            return ["Problem", "Approach", "Solution", "Complexity"]
        if action in {"code", "implementation", "build"}:
            return ["Approach", "Code", "Explanation", "Complexity"]
        if action in {"definition", "define"} or raw_text.startswith("what is "):
            return ["Definition", "Example", "Key Points"]

        return ["Definition", "Explanation", "Example", "Key Points", "Applications"]

    def _generate_unknown_topic_outline(
        self,
        context: OrchestratedContext,
        llm_client: object,
    ) -> list[str]:
        topic = context.knowledge.topic
        prompt = "\n".join(
            [
                f"Topic: {topic}",
                f"User question: {context.intent.raw_text}",
                "",
                "Return ONLY a JSON array of 4-6 teaching headings.",
                "Rules:",
                "- Ordered from beginner to advanced.",
                "- Short heading names only.",
                "- No explanations.",
                "- No markdown.",
                "- No extra text.",
                '- Example: ["Definition","Working","Example","Complexity","Applications"]',
            ]
        )
        for _attempt in range(2):
            try:
                raw_outline = llm_client.generate_text(  # type: ignore[attr-defined]
                    system_prompt=self.outline_system_prompt,
                    user_content=prompt,
                    temperature=0.0,
                )
            except Exception:
                return []

            outline = self._validate_outline(raw_outline)
            if outline:
                return outline
        return []

    @staticmethod
    def _validate_outline(raw_outline: str) -> list[str]:
        try:
            parsed = json.loads(raw_outline)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []

        headings: list[str] = []
        seen: set[str] = set()
        for item in parsed:
            if not isinstance(item, str):
                return []
            heading = " ".join(item.strip().split())
            if not heading or len(heading) > 40:
                return []
            key = heading.lower()
            if key in seen:
                continue
            seen.add(key)
            headings.append(heading)

        if not 4 <= len(headings) <= 6:
            return []
        return headings

    @staticmethod
    def _mode_rules(response_mode: str, has_remaining_headings: bool) -> list[str]:
        if response_mode == "lesson":
            rules = [
                "- The application decides the lesson outline; do not create your own outline.",
                "- Explain ONLY the headings listed under 'Headings to explain now'.",
                "- Keep those headings exactly as provided.",
                "- Do not rename, merge, reorder, skip, or create additional headings.",
                "- Explain only the first 3 supplied sections.",
                "- Never start a fourth section.",
                "- Stop after the last supplied heading.",
                "- Finish every supplied heading completely, and never begin a heading that cannot be completed.",
            ]
            if has_remaining_headings:
                rules.append(
                    "- End exactly with: 'Would you like me to explain the remaining sections?'"
                )
            return rules

        if response_mode == "coding":
            return [
                "- Coding mode: do not use lesson headings or the lesson planner.",
                "- Generate code normally for the user's coding request.",
                "- Do not use the Application-selected lesson outline.",
                "- Do not force Definition, Working, Example, or other teaching headings.",
                "- If the requested code is too large, stop only at a natural boundary such as the end of a function, class, or file.",
                "- Never stop in the middle of a line, expression, block, or code fence.",
                "- If more code remains, end exactly with: \"I've completed this part. Reply 'Continue' to generate the remaining code.\"",
            ]

        if response_mode == "list":
            return [
                "- LIST mode: return only the requested list.",
                "- The entire response must be only bullet lines.",
                "- Each line must start with '- '.",
                "- Do not use numbered lists.",
                "- Do not write an introduction.",
                "- Answer the exact list request from the user's message.",
                "- Do not explain items.",
                "- Do not summarize items.",
                "- Do not add information beyond the requested list items.",
                "- Do not add conclusions.",
                "- Do not add study advice.",
                "- Do not add a next step or follow-up question.",
                "- Do not continue after the list.",
            ]

        if response_mode == "summary":
            return [
                "- SUMMARY mode: summarize only what the user requested.",
                "- Keep the summary compact.",
                "- Do not expand into a lesson unless the user asks.",
                "- Do not add practice questions, advice, or next steps.",
            ]

        return [
            "- QA mode: do not use lesson planning.",
            "- Answer normally using the dialogue manager rules.",
            "- Do not force lesson headings unless the user explicitly asks for a structured lesson.",
        ]

    @staticmethod
    def _normalize_topic(topic: str) -> str:
        normalized = topic.strip().lower().replace("-", " ")
        for prefix in ("what is ", "explain ", "teach me ", "learn ", "study "):
            if normalized.startswith(prefix):
                normalized = normalized.removeprefix(prefix)
                break
        return " ".join(normalized.split())

    @staticmethod
    def _numbered_lines(items: list[str]) -> list[str]:
        return [f"{index}. {item}" for index, item in enumerate(items, start=1)]

    @staticmethod
    def _plain_lines(items: list[str]) -> list[str]:
        return [f"- {item}" for item in items]
