"""Central orchestrator for information diffusion between tutor agents."""

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass

from backend.agents.conversation_state_agent import ConversationStateAgent
from backend.agents.dialogue_manager_agent import DialogueManagerAgent
from backend.agents.intent_agent import IntentAgent
from backend.agents.knowledge_agent import KnowledgeAgent
from backend.agents.memory_agent import MemoryAgent
from backend.agents.reflection_agent import ReflectionAgent
from backend.agents.response_generation_agent import ResponseGenerationAgent
from backend.agents.teaching_planner_agent import TeachingPlannerAgent
from backend.database.chroma_repository import ChromaChatRepository
from backend.llm.ollama_client import OllamaClient
from backend.memory.hygiene import (
    is_essential_learning_text,
    is_low_signal_text,
    is_memory_control_request,
    is_polluted_memory_text,
)
from backend.models.chat import Message
from backend.models.learner import MemoryContextItem, MemorySignal, OrchestratedContext


logger = logging.getLogger(__name__)


@dataclass
class LessonSelection:
    full_outline: list[str]
    selected_headings: list[str]
    remaining_headings: list[str]


_RECALL_STOPWORDS = {
    "a",
    "about",
    "abt",
    "any",
    "between",
    "can",
    "did",
    "do",
    "does",
    "have",
    "he",
    "i",
    "in",
    "it",
    "me",
    "of",
    "oh",
    "or",
    "our",
    "ppl",
    "people",
    "person",
    "persons",
    "smth",
    "something",
    "that",
    "the",
    "there",
    "this",
    "to",
    "two",
    "u",
    "we",
    "what",
    "with",
}


class TutorOrchestrator:
    """Coordinate specialized agents through progressive information diffusion."""

    def __init__(
        self,
        repository: ChromaChatRepository,
        llm_client: OllamaClient | None = None,
        *,
        working_memory_limit: int = 10,
    ) -> None:
        self._repository = repository
        self._llm_client = llm_client
        self._intent_agent = IntentAgent()
        self._conversation_state_agent = ConversationStateAgent()
        self._memory_agent = MemoryAgent(
            repository,
            llm_client,
            working_memory_limit=working_memory_limit,
        )
        self._knowledge_agent = KnowledgeAgent()
        self._reflection_agent = ReflectionAgent(repository)
        self._teaching_planner_agent = TeachingPlannerAgent()
        self._dialogue_manager_agent = DialogueManagerAgent()
        self._response_generation_agent = ResponseGenerationAgent()
        self._last_context: OrchestratedContext | None = None
        self._lesson_continuations: dict[str, list[str]] = {}
        self._code_continuations: set[str] = set()

    def generate_reply(self, chat_id: str, user_message: Message) -> str:
        context = self._build_context(user_message)
        self._last_context = context
        response_mode = self._response_mode(chat_id, user_message, context)
        structured_context = self._structured_context_for_response(
            user_message,
            context.memory_context,
        )
        explicit_memory_request = bool(structured_context)

        if response_mode != "coding" and self._should_use_controlled_reply(context):
            return self._response_generation_agent.fallback_reply(context)

        if self._llm_client is None:
            return self._response_generation_agent.fallback_reply(context)

        lesson_selection = (
            self._lesson_selection(chat_id, context)
            if response_mode == "lesson"
            else LessonSelection(full_outline=[], selected_headings=[], remaining_headings=[])
        )
        reply = self._llm_client.generate_reply(
            self._response_generation_agent.select_messages(context),
            system_prompt=self._response_generation_agent.system_prompt(
                context,
                response_mode=response_mode,
                structured_context=structured_context,
                explicit_memory_request=explicit_memory_request,
                selected_headings=lesson_selection.selected_headings,
                remaining_headings=lesson_selection.remaining_headings,
                full_outline=lesson_selection.full_outline,
            ),
        )
        self._commit_response_mode(chat_id, response_mode, lesson_selection)
        return reply

    def stream_reply(self, chat_id: str, user_message: Message) -> Iterator[str]:
        context = self._build_context(user_message)
        self._last_context = context
        response_mode = self._response_mode(chat_id, user_message, context)
        structured_context = self._structured_context_for_response(
            user_message,
            context.memory_context,
        )
        explicit_memory_request = bool(structured_context)

        if response_mode != "coding" and self._should_use_controlled_reply(context):
            yield from self._chunk_static_reply(
                self._response_generation_agent.fallback_reply(context)
            )
            return

        if self._llm_client is None:
            yield from self._chunk_static_reply(
                self._response_generation_agent.fallback_reply(context)
            )
            return

        lesson_selection = (
            self._lesson_selection(chat_id, context)
            if response_mode == "lesson"
            else LessonSelection(full_outline=[], selected_headings=[], remaining_headings=[])
        )
        yield from self._llm_client.stream_reply(
            self._response_generation_agent.select_messages(context),
            system_prompt=self._response_generation_agent.system_prompt(
                context,
                response_mode=response_mode,
                structured_context=structured_context,
                explicit_memory_request=explicit_memory_request,
                selected_headings=lesson_selection.selected_headings,
                remaining_headings=lesson_selection.remaining_headings,
                full_outline=lesson_selection.full_outline,
            ),
        )
        self._commit_response_mode(chat_id, response_mode, lesson_selection)

    def _structured_context_for_response(
        self,
        user_message: Message,
        memory_context: list[MemoryContextItem],
    ) -> list[str]:
        if self._asks_to_resume_previous_topic(user_message.content):
            return self._resume_previous_topic_context(user_message)
        if self._asks_to_list_discussed_topics(user_message.content):
            return self._discussed_topics_context(user_message)
        if self._asks_about_project_memory(user_message.content):
            return self._project_memory_context(memory_context)
        if self._asks_about_durable_user_memory(user_message.content):
            return self._durable_memory_profile_context(memory_context)
        if self._asks_targeted_history_question(user_message.content):
            return self._episodic_recall_context(user_message)
        if self._asks_for_conversation_summary(user_message.content):
            return self._conversation_summary_context(user_message)
        if self._asks_about_first_saved_conversation(user_message.content):
            return self._first_memory_context(user_message)
        return []

    def _resume_previous_topic_context(self, user_message: Message) -> list[str]:
        meaningful_turns = self._meaningful_prior_user_turns(user_message)
        if not meaningful_turns:
            return [
                "memory_history_request: resume_previous_topic",
                "status: no meaningful prior learning topic found",
            ]
        latest = meaningful_turns[-1]
        return [
            "memory_history_request: resume_previous_topic",
            f"latest_topic: {self._compact_summary_line(latest.content, max_length=120)}",
            "instruction: do not dump a timeline; ask whether the learner wants recap, depth, or practice",
        ]

    def _discussed_topics_context(self, user_message: Message) -> list[str]:
        topics = self._discussed_topic_names(user_message)
        if not topics:
            return [
                "memory_history_request: list_discussed_topics",
                "status: no meaningful learning topics found",
            ]
        return [
            "memory_history_request: list_discussed_topics",
            "instruction: return only these topics as bullets; do not explain them",
            *[f"topic: {topic}" for topic in topics[-10:]],
        ]

    @staticmethod
    def _project_memory_context(memory_context: list[MemoryContextItem]) -> list[str]:
        project_items = [
            item
            for item in memory_context
            if re.search(
                r"\b(?:project|built|building|implemented|worked on|app|api|chatbot|tutor)\b",
                item.content,
                re.I,
            )
        ]
        if not project_items:
            return [
                "memory_history_request: project_memory",
                "status: no retrieved project memories found",
            ]
        return [
            "memory_history_request: project_memory",
            "instruction: summarize only the retrieved project-related memories",
            *[f"{item.type}: {item.content}" for item in project_items[:5]],
        ]

    def _durable_memory_profile_context(
        self,
        memory_context: list[MemoryContextItem],
    ) -> list[str]:
        profile_items = [
            item
            for item in memory_context
            if self._is_profile_memory_type(item.type)
            and not is_polluted_memory_text(item.content)
        ]
        if not profile_items:
            return [
                "memory_history_request: durable_user_memory",
                "status: no relevant durable profile memories retrieved",
            ]
        return [
            "memory_history_request: durable_user_memory",
            "instruction: summarize durable learner memories only; do not quote chat transcript",
            *[
                f"{self._memory_profile_section(item.type)}: {self._clean_memory_text(item.content)}"
                for item in profile_items[:8]
            ],
        ]

    def _episodic_recall_context(self, user_message: Message) -> list[str]:
        query_terms = self._recall_terms(user_message.content)
        if not query_terms:
            return []
        prior_messages = [
            message
            for message in self._repository.list_user_messages(user_message.user_id)
            if message.id != user_message.id
            and message.content.strip()
            and not is_low_signal_text(message.content)
            and not is_memory_control_request(message.content)
        ]
        matches = self._rank_recall_matches(query_terms, prior_messages)
        if not matches:
            return [
                "memory_history_request: targeted_history_lookup",
                f"query_terms: {' '.join(query_terms)}",
                "status: no matching prior discussion found",
            ]
        return [
            "memory_history_request: targeted_history_lookup",
            f"query_terms: {' '.join(query_terms)}",
            *[f"match: {self._compact_summary_line(message.content)}" for message in matches[:3]],
        ]

    def _conversation_summary_context(self, user_message: Message) -> list[str]:
        learner_turns = self._meaningful_prior_user_turns(user_message)
        if not learner_turns:
            return [
                "memory_history_request: conversation_summary",
                "status: only short casual turns found",
            ]
        return [
            "memory_history_request: conversation_summary",
            "instruction: summarize current chat history only; do not use Chroma memories",
            *[
                f"learning_turn: {self._compact_summary_line(message.content)}"
                for message in learner_turns[-8:]
            ],
        ]

    def _first_memory_context(self, user_message: Message) -> list[str]:
        memories = [
            memory
            for memory in self._repository.list_memories(user_message.user_id)
            if self._is_recallable_permanent_memory(memory.type)
        ]
        if not memories:
            return [
                "memory_history_request: first_permanent_memory",
                "status: no permanent learning memory stored",
            ]
        first_memory = min(memories, key=lambda item: item.timestamp)
        return [
            "memory_history_request: first_permanent_memory",
            f"timestamp: {self._format_time(first_memory.timestamp)}",
            f"memory: {first_memory.memory}",
        ]

    @staticmethod
    def _chunk_static_reply(reply: str, chunk_size: int = 12) -> Iterator[str]:
        for index in range(0, len(reply), chunk_size):
            yield reply[index : index + chunk_size]

    def record_assistant_reply(self, assistant_message: Message) -> None:
        # Permanent memory is reserved for durable learner facts. Assistant
        # replies remain in the chat transcript, but storing every tutor action
        # as long-term memory makes retrieval slower and noisier.
        return

    def _response_mode(
        self,
        chat_id: str,
        user_message: Message,
        context: OrchestratedContext,
    ) -> str:
        content = user_message.content
        if self._asks_for_code_continuation(content) and chat_id in self._code_continuations:
            return "coding"
        if self._asks_for_lesson_continuation(content) and chat_id in self._lesson_continuations:
            return "lesson"
        if self._is_coding_request(content):
            return "coding"
        if self._is_list_request(content):
            return "list"
        if self._is_summary_request(content):
            return "summary"
        if self._is_lesson_request(content, context):
            return "lesson"
        return "qa"

    @staticmethod
    def _asks_for_code_continuation(content: str) -> bool:
        return bool(re.fullmatch(r"\s*(?:continue|go on|keep going)\s*[.!?]?\s*", content, re.I))

    @staticmethod
    def _asks_for_lesson_continuation(content: str) -> bool:
        return bool(re.fullmatch(r"\s*(?:continue|go on|keep going|next)\s*[.!?]?\s*", content, re.I))

    @staticmethod
    def _is_coding_request(content: str) -> bool:
        text = content.lower()
        return bool(
            re.search(
                r"\b(?:code|coding|implement|implementation|debug|fix|bug|error|traceback|exception|api|endpoint|fastapi|react|component|function|class|script|project|build|create app|write a program|program)\b",
                text,
            )
        )

    @staticmethod
    def _is_lesson_request(content: str, context: OrchestratedContext) -> bool:
        text = content.lower().strip()
        if TutorOrchestrator._is_coding_request(content):
            return False
        if context.conversation_state.state == "progression":
            return True
        return bool(
            re.search(r"\b(?:explain|teach me|describe)\b", text)
            or re.search(r"^what\s+is\b", text)
            or re.search(r"^how\s+does\b.*\bwork\b", text)
        )

    @staticmethod
    def _is_list_request(content: str) -> bool:
        text = content.lower().strip()
        return bool(
            re.search(r"^(?:list|show|name|tell me)\b.*\b(?:topics?|items?|things?|concepts?)\b", text)
            or re.search(r"^(?:what|which)\b.*\b(?:topics?|concepts?)\b", text)
        )

    @staticmethod
    def _is_summary_request(content: str) -> bool:
        text = content.lower().strip()
        return bool(re.search(r"\b(?:summarize|summary|recap)\b", text))

    def _lesson_selection(
        self,
        chat_id: str,
        context: OrchestratedContext,
    ) -> LessonSelection:
        if context.conversation_state.state == "progression":
            stored_headings = self._lesson_continuations.get(chat_id, [])
            if stored_headings:
                selected = stored_headings[: self._response_generation_agent.max_selected_headings]
                remaining = stored_headings[
                    self._response_generation_agent.max_selected_headings :
                ]
                return LessonSelection(
                    full_outline=stored_headings,
                    selected_headings=selected,
                    remaining_headings=remaining,
                )

        full_outline = self._response_generation_agent.lesson_outline(
            context,
            self._llm_client,
        )
        selected = full_outline[: self._response_generation_agent.max_selected_headings]
        remaining = full_outline[self._response_generation_agent.max_selected_headings :]
        return LessonSelection(
            full_outline=full_outline,
            selected_headings=selected,
            remaining_headings=remaining,
        )

    def _commit_response_mode(
        self,
        chat_id: str,
        response_mode: str,
        lesson_selection: LessonSelection,
    ) -> None:
        if response_mode == "lesson" and lesson_selection.remaining_headings:
            self._lesson_continuations[chat_id] = lesson_selection.remaining_headings
        else:
            self._lesson_continuations.pop(chat_id, None)

        if response_mode == "coding":
            self._code_continuations.add(chat_id)
        else:
            self._code_continuations.discard(chat_id)

    def _meaningful_prior_user_turns(self, user_message: Message) -> list[Message]:
        return [
            message
            for message in self._repository.list_user_messages(user_message.user_id)
            if message.id != user_message.id
            and message.role == "user"
            and self._is_summary_worthy_turn(message.content)
        ]

    def _discussed_topic_names(self, user_message: Message) -> list[str]:
        return self._dedupe_preserve_order(
            [
                topic
                for message in self._meaningful_prior_user_turns(user_message)
                if (topic := self._topic_name_from_turn(message.content))
            ]
        )

    @staticmethod
    def _asks_for_conversation_summary(content: str) -> bool:
        text = content.lower()
        if TutorOrchestrator._asks_to_list_discussed_topics(content):
            return False
        if TutorOrchestrator._asks_to_resume_previous_topic(content):
            return False
        return bool(
            re.search(
                r"\bwhat\b.*\b(?:discuss(?:ed)?|talk(?:ed)? about|cover(?:ed)?|learn(?:ed)?)\b",
                text,
            )
            or re.search(
                r"\b(?:summary|summarize|recap)\b.*\b(?:chat|conversation|discuss|talk|we|our)\b",
                text,
            )
            or re.search(
                r"\b(?:remember|forgot)\b.*\b(?:chat|conversation|discuss|talk|summary|recap)\b",
                text,
            )
        )

    @staticmethod
    def _asks_to_list_discussed_topics(content: str) -> bool:
        text = content.lower().strip()
        list_pattern = r"^(?:list|show|name|tell me|what|which)\b.*\b(?:topics?|concepts?)\b"
        history_reference = (
            r"(?:\b(?:we|our|us)\b.*\b(?:discussed|covered|learned|talked about)\b"
            r"|\b(?:discussed|covered|learned|talked about)\b.*\b(?:we|our|us)\b)"
        )
        return bool(
            re.search(list_pattern, text)
            and re.search(history_reference, text)
        )

    @staticmethod
    def _topic_name_from_turn(content: str) -> str:
        text = " ".join(content.strip().split())
        patterns = (
            r"^(?:can you|can u|please)?\s*(?:explain|teach me|describe)\s+(.+)$",
            r"^what\s+is\s+(.+)$",
            r"^how\s+does\s+(.+?)\s+work\??$",
            r"^(?:i\s+(?:want to learn|am learning|learned|mastered|completed))\s+(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return TutorOrchestrator._clean_topic_name(match.group(1))
        return TutorOrchestrator._clean_topic_name(text)

    @staticmethod
    def _clean_topic_name(topic: str) -> str:
        cleaned = re.sub(r"[?.!]+$", "", topic.strip())
        cleaned = re.sub(r"\b(?:in detail|please|pls)\b", "", cleaned, flags=re.I)
        cleaned = " ".join(cleaned.split())
        aliases = {
            "dfs": "Depth First Search (DFS)",
            "depth first search": "Depth First Search (DFS)",
            "bst": "Binary Search Tree (BST)",
            "binary search tree": "Binary Search Tree (BST)",
        }
        return aliases.get(cleaned.lower(), cleaned)

    @staticmethod
    def _asks_targeted_history_question(content: str) -> bool:
        text = content.lower()
        return bool(
            re.search(
                r"\b(?:did|have)\b.*\b(?:discuss|talk|cover|mention|ask)\b",
                text,
            )
            or re.search(
                r"\b(?:do u remember|do you remember|remember)\b.*\b(?:about|when|story|topic|question)\b",
                text,
            )
        ) and not TutorOrchestrator._asks_for_conversation_summary(content)

    @staticmethod
    def _asks_about_durable_user_memory(content: str) -> bool:
        text = content.lower()
        return bool(
            re.search(r"\bwhat\b.*\b(?:remember|know)\b.*\babout me\b", text)
            or re.search(r"\bwhat\b.*\blearned\b.*\babout me\b", text)
            or re.search(
                r"\b(?:summarize|summary)\b.*\b(?:everything|all)\b.*\b(?:learned|know|remember)\b.*\babout me\b",
                text,
            )
        )

    @staticmethod
    def _asks_about_project_memory(content: str) -> bool:
        text = content.lower()
        return bool(
            re.search(r"\bwhat\b.*\bprojects?\b.*\b(?:worked on|built|made|implemented|done)\b", text)
            or re.search(r"\bwhich\b.*\bprojects?\b.*\b(?:worked on|built|made|implemented|done)\b", text)
            or re.search(r"\bprojects?\b.*\b(?:worked on|built|made|implemented|done)\b", text)
        )

    @staticmethod
    def _asks_to_resume_previous_topic(content: str) -> bool:
        text = content.lower()
        return bool(
            re.search(
                r"\b(?:continue|resume|carry on|go back to|pick up)\b.*\b(?:earlier|previous|last|where we left|what we discussed)\b",
                text,
            )
            or re.search(
                r"\b(?:can we|could we|lets|let's)\b.*\bcontinue\b.*\b(?:discussed|earlier|previous)\b",
                text,
            )
        )

    @staticmethod
    def _recall_terms(content: str) -> list[str]:
        normalized = (
            content.lower()
            .replace("ppl", "people")
            .replace("abt", "about")
            .replace("smth", "something")
        )
        normalized = re.sub(r"[^a-z0-9+#. ]+", " ", normalized)
        return [
            token
            for token in normalized.split()
            if len(token) > 1 and token not in _RECALL_STOPWORDS
        ]

    @staticmethod
    def _rank_recall_matches(
        query_terms: list[str],
        messages: list[Message],
    ) -> list[Message]:
        query_set = set(query_terms)

        def score(message: Message) -> int:
            text = message.content.lower().replace("ppl", "people")
            tokens = set(re.sub(r"[^a-z0-9+#. ]+", " ", text).split())
            overlap = len(query_set & tokens)
            phrase_bonus = sum(1 for term in query_set if term in text)
            role_bonus = 1 if message.role == "user" else 0
            return (overlap * 3) + phrase_bonus + role_bonus

        scored = [(score(message), message) for message in messages]
        return [
            message
            for score_value, message in sorted(
                scored,
                key=lambda item: (item[0], item[1].timestamp),
                reverse=True,
            )
            if score_value >= 3
        ]

    @staticmethod
    def _is_low_signal_turn(content: str) -> bool:
        return is_low_signal_text(content)

    @staticmethod
    def _is_summary_worthy_turn(content: str) -> bool:
        return (
            is_essential_learning_text(content)
            and not is_low_signal_text(content)
            and not is_memory_control_request(content)
        )

    @staticmethod
    def _compact_summary_line(content: str, max_length: int = 160) -> str:
        text = " ".join(content.strip().split())
        if len(text) <= max_length:
            return text
        return f"{text[: max_length - 1].rstrip()}…"

    @staticmethod
    def _memory_profile_section(memory_type: str) -> str:
        return {
            "goal": "Goals",
            "preference": "Preferences",
            "knowledge_state": "Knowledge",
            "learning_difficulty": "Learning Difficulties",
            "achievement": "Achievements",
            "fact": "Profile / Facts",
        }.get(memory_type, "Profile / Facts")

    @staticmethod
    def _clean_memory_text(memory: str) -> str:
        text = " ".join(memory.strip().split())
        prefixes = (
            "Student goal: ",
            "Learning preference: ",
            "Learning difficulty: ",
            "Achievement: ",
            "Fact discussed: ",
            "Knowledge state: ",
        )
        for prefix in prefixes:
            if text.startswith(prefix):
                return text.removeprefix(prefix)
        return text

    @staticmethod
    def _dedupe_preserve_order(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def _asks_about_first_saved_conversation(content: str) -> bool:
        text = content.lower()
        return bool(
            re.search(
                r"\bfirst\b.*\b(?:conversation|converse|talk|chat|message|time)\b",
                text,
            )
            or re.search(
                r"\b(?:when|what)\b.*\bfirst\b.*\b(?:meet|talk|chat|message)\b",
                text,
            )
        )

    @staticmethod
    def _format_time(value: object) -> str:
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d at %H:%M UTC")  # type: ignore[no-any-return]
        return str(value)

    @staticmethod
    def _is_recallable_permanent_memory(memory_type: str) -> bool:
        return memory_type in {
            "goal",
            "knowledge_state",
            "learning_difficulty",
            "preference",
            "achievement",
            "fact",
            "preference",
            "study_plan",
            "achievement",
            "weak_topic",
            "strong_topic",
            "completed_topic",
            "learning_event",
        }

    @staticmethod
    def _is_profile_memory_type(memory_type: str) -> bool:
        return memory_type.strip().lower().replace("-", "_").replace(" ", "_") in {
            "fact",
            "goal",
            "preference",
            "achievement",
            "learning_difficulty",
            "learning_style",
            "profile",
        }

    @staticmethod
    def _should_use_controlled_reply(context: OrchestratedContext) -> bool:
        return context.dialogue.conversation_type in {
            "gratitude",
            "goodbye",
            "greeting",
            "excitement",
            "casual_chat",
            "confusion",
            "understanding",
            "correction",
            "disagreement",
        }

    def _build_context(self, user_message: Message) -> OrchestratedContext:
        intent = self._intent_agent.analyze(user_message.content)
        self._log_agent("Intent Agent", {"content": user_message.content}, intent)

        conversation_state = self._conversation_state_agent.classify(intent)
        self._log_agent("Conversation State Agent", intent, conversation_state)

        memory = self._memory_agent.process(
            user_message=user_message,
            intent=intent,
            conversation_state=conversation_state,
        )
        self._log_agent("Memory Agent", conversation_state, memory)

        memory_context = self._memory_context_from_signal(memory)
        logger.warning(
            "[MEMORY DEBUG] Memory Retrieval Context built count=%s",
            len(memory_context),
        )
        for index, item in enumerate(memory_context, start=1):
            logger.warning(
                "[MEMORY DEBUG] Memory Retrieval Context %s type=%s topic=%s content=%s",
                index,
                item.type,
                item.topic or "",
                self._compact_summary_line(item.content),
            )
        self._log_agent("Memory Retrieval Context", memory, memory_context)

        knowledge = self._knowledge_agent.enrich(
            intent=intent,
            conversation_state=conversation_state,
            memory=memory,
        )
        self._log_agent("Knowledge Agent", memory, knowledge)

        reflection = self._reflection_agent.reflect(user_message.user_id, memory)
        self._log_agent("Reflection Agent", memory, reflection)

        plan = self._teaching_planner_agent.plan(
            conversation_state=conversation_state,
            memory=memory,
            knowledge=knowledge,
            reflection=reflection,
        )
        self._log_agent("Teaching Planner Agent", reflection, plan)

        dialogue = self._dialogue_manager_agent.calibrate(
            intent=intent,
            conversation_state=conversation_state,
            plan=plan,
        )
        self._log_agent("Dialogue Manager", plan, dialogue)

        context = OrchestratedContext(
            intent=intent,
            conversation_state=conversation_state,
            memory=memory,
            memory_context=memory_context,
            knowledge=knowledge,
            reflection=reflection,
            plan=plan,
            dialogue=dialogue,
        )
        self._log_agent("Response Generation Agent", dialogue, context)
        return context

    @staticmethod
    def _memory_context_from_signal(memory: MemorySignal) -> list[MemoryContextItem]:
        return [
            MemoryContextItem(
                type=item.record.type,
                content=item.record.memory,
                topic=item.record.topic,
                score=item.total_score,
            )
            for item in memory.retrieved_memories
            if item.record.status == "active"
        ]

    def _log_agent(self, name: str, agent_input: object, agent_output: object) -> None:
        logger.info(
            "%s input=%s output=%s",
            name,
            self._jsonish(agent_input),
            self._jsonish(agent_output),
        )

    @staticmethod
    def _jsonish(value: object) -> str:
        if hasattr(value, "model_dump_json"):
            return value.model_dump_json()  # type: ignore[no-any-return]
        return str(value)
