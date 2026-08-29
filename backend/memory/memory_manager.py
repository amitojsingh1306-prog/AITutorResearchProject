"""MemGPT-inspired memory manager for the AI tutor.

This is the central policy object for the simplified research implementation.
It mirrors the key MemGPT idea, but in a lightweight educational form:

- Working memory is the active, limited prompt context.
- Long-term memory is persistent external storage.
- The manager decides what gets promoted out of working memory.
- Relevant long-term memories are retrieved before every model response.

The rest of the chatbot receives a regular ``MemorySignal`` and does not need
to know whether the backend is a buffer, rolling summary, vector store, graph
store, or hybrid memory system.
"""

from __future__ import annotations

import json
import logging
import re
from uuid import uuid4

from backend.llm.ollama_client import OllamaClient, OllamaClientError
from backend.memory.hygiene import (
    is_essential_learning_text,
    is_low_signal_text,
    is_memory_control_request,
)
from backend.models.chat import Message
from backend.models.learner import (
    ConversationStateSignal,
    IntentSignal,
    LearnerProfile,
    MemoryDecision,
    MemoryRecord,
    MemorySignal,
    RetrievedMemory,
    StudentMemoryObject,
)

from .memory_store import LongTermMemoryStore
from .retrieval import MemoryRetriever
from .working_memory import WorkingMemory


logger = logging.getLogger(__name__)


class MemoryManager:
    """Coordinate working memory, long-term promotion, and retrieval."""

    _known_topic_aliases = {
        "langgraph": "LangGraph",
        "stategraph": "StateGraph",
        "conditional edges": "Conditional Edges",
        "nodes": "Nodes",
        "edges": "Edges",
        "rag": "RAG",
        "fastapi": "FastAPI",
        "chromadb": "ChromaDB",
        "python": "Python",
        "nlp": "NLP",
        "memgpt": "MemGPT",
        "memory manager": "Memory Manager",
        "vector memory": "Vector Memory",
        "graph memory": "Graph Memory",
        "hybrid memory": "Hybrid Memory",
        "recursion": "Recursion",
        "base case": "Recursion",
        "call stack": "Recursion",
        "sql joins": "SQL Joins",
        "joins": "SQL Joins",
        "inner join": "SQL Joins",
        "outer join": "SQL Joins",
        "linked list": "Linked Lists",
        "linked lists": "Linked Lists",
        "binary search tree": "Binary Search Tree",
        "bst": "Binary Search Tree",
    }

    def __init__(
        self,
        *,
        store: LongTermMemoryStore,
        retriever: MemoryRetriever,
        working_memory: WorkingMemory,
        llm_client: OllamaClient | None = None,
    ) -> None:
        self._store = store
        self._retriever = retriever
        self._working_memory = working_memory
        self._llm_client = llm_client

    def process_turn(
        self,
        *,
        user_message: Message,
        conversation_messages: list[Message],
        intent: IntentSignal,
        conversation_state: ConversationStateSignal,
    ) -> MemorySignal:
        """Update memory state and retrieve prompt memories for this turn.

        The current user message always remains in working memory because it is
        part of the active conversation. Only stable, important information is
        promoted into long-term memory.
        """

        working_messages = self._working_memory.select_context(conversation_messages)
        retrieval_query = self._retrieval_query(intent, conversation_state)
        retrieval_mode = self._retrieval_mode(intent.raw_text)
        chroma_enabled = retrieval_mode != "CURRENT_CONVERSATION"
        logger.warning(
            '[MEMORY ROUTER] query="%s" mode=%s chroma_enabled=%s',
            self._safe_summary(intent.raw_text),
            retrieval_mode,
            chroma_enabled,
        )
        relevant_memories = (
            self._retriever.retrieve(
                user_id=user_message.user_id,
                query=retrieval_query,
            )
            if chroma_enabled
            else []
        )
        existing_memories = [
            memory
            for memory in self._store.list_memories(user_message.user_id)
            if memory.status == "active"
        ]
        memory_candidates = self._unique_memories(
            [
                item.record
                for item in relevant_memories
                if item.record.status == "active"
            ],
            existing_memories,
        )
        decision = self._decide_memory_operation(
            user_message=user_message,
            intent=intent,
            conversation_state=conversation_state,
            relevant_memories=memory_candidates,
        )
        changed_memories = self._execute_decision(
            decision=decision,
            user_message=user_message,
            intent=intent,
            relevant_memories=memory_candidates,
        )

        all_memories = [
            memory
            for memory in self._store.list_memories(user_message.user_id)
            if memory.status == "active"
        ]
        self._log_evolved_memories(user_message.user_id, all_memories)
        profile = self._profile_from_memories(user_message.user_id, all_memories)
        self._store.save_learner_profile(profile)

        updated_retrieved_memories = (
            self._retriever.retrieve(
                user_id=user_message.user_id,
                query=retrieval_query,
            )
            if chroma_enabled
            else []
        )
        prompt_memories = self._prompt_memories(
            retrieved=updated_retrieved_memories,
            all_memories=all_memories,
            current_message_id=user_message.id,
        )
        return MemorySignal(
            profile=profile,
            decision=decision,
            stored_memories=changed_memories,
            retrieved_memories=prompt_memories,
            memories=all_memories,
            working_messages=working_messages,
        )

    def store_assistant_experience(
        self,
        *,
        assistant_message: Message,
        topic: str,
    ) -> MemoryRecord:
        raise RuntimeError("Assistant replies are not stored as long-term memories.")

    def list_active_memories(self, user_id: str) -> list[MemoryRecord]:
        """Return durable active memories without reading chat transcripts."""

        return [
            memory
            for memory in self._store.list_memories(user_id)
            if memory.status == "active"
        ]

    def _decide_memory_operation(
        self,
        *,
        user_message: Message,
        intent: IntentSignal,
        conversation_state: ConversationStateSignal,
        relevant_memories: list[MemoryRecord],
    ) -> MemoryDecision:
        if re.search(r"\b(?:forget|delete|remove)\b", user_message.content, re.I):
            return self._fallback_memory_decision(
                user_message=user_message,
                intent=intent,
                conversation_state=conversation_state,
                relevant_memories=relevant_memories,
            )

        if is_low_signal_text(user_message.content) or is_memory_control_request(
            user_message.content
        ):
            return MemoryDecision(
                action="NOOP",
                reason="The message is temporary conversational context.",
            )

        if self._llm_client is not None:
            try:
                return self._llm_memory_decision(
                    user_message=user_message,
                    relevant_memories=relevant_memories,
                )
            except (AttributeError, OllamaClientError, ValueError, json.JSONDecodeError):
                pass

        return self._fallback_memory_decision(
            user_message=user_message,
            intent=intent,
            conversation_state=conversation_state,
            relevant_memories=relevant_memories,
        )

    def _execute_decision(
        self,
        *,
        decision: MemoryDecision,
        user_message: Message,
        intent: IntentSignal,
        relevant_memories: list[MemoryRecord],
    ) -> list[MemoryRecord]:
        action = decision.action.upper()
        if action in {"NOOP", ""}:
            return []
        if action == "DELETE":
            if decision.target_memory_id:
                self._store.delete_memory(decision.target_memory_id)
            return []

        if action not in {"ADD", "UPDATE"}:
            return []

        raw_memory = (decision.memory or user_message.content).strip()
        structured_memory = self._extract_student_memory(
            raw_memory=raw_memory,
            category=decision.category,
            user_message=user_message,
            intent=intent,
        )

        # A-MEM-style evolution: before creating a new memory, search related
        # memories and evolve the closest one so repeated learning events become
        # one richer student memory instead of duplicate Chroma documents.
        target_memory = self._target_memory_for_evolution(
            action=action,
            decision=decision,
            new_memory=structured_memory,
            relevant_memories=relevant_memories,
        )
        if target_memory is not None:
            action = "UPDATE"
            memory_id = target_memory.id
            structured_memory = self._evolve_student_memory(
                existing=target_memory,
                new_memory=structured_memory,
            )
        else:
            memory_id = (
                decision.target_memory_id
                if action == "UPDATE" and decision.target_memory_id
                else str(uuid4())
            )

        memory = MemoryRecord(
            id=memory_id,
            user_id=user_message.user_id,
            timestamp=user_message.timestamp,
            memory=structured_memory.model_dump_json(exclude_none=True),
            importance=self._importance_for_category(decision.category),
            type=self._normalize_category(decision.category),
            topic=structured_memory.topic or self._topic_from_intent_or_text(intent),
            status="active",
            source_message_id=user_message.id,
        )
        return [self._store.save_memory(memory)]

    def _llm_memory_decision(
        self,
        *,
        user_message: Message,
        relevant_memories: list[MemoryRecord],
    ) -> MemoryDecision:
        if self._llm_client is None:
            raise ValueError("No LLM client configured.")

        payload = {
            "user_message": user_message.content,
            "existing_memories": [
                {
                    "id": memory.id,
                    "category": memory.type,
                    "memory": memory.memory,
                    "topic": memory.topic,
                }
                for memory in relevant_memories[:8]
            ],
        }
        response = self._llm_client.generate_text(
            system_prompt=self._memory_decision_prompt(),
            user_content=json.dumps(payload, ensure_ascii=True),
            temperature=0.0,
        )
        data = json.loads(self._json_object(response))
        decision = MemoryDecision.model_validate(data)
        return decision.model_copy(update={"action": decision.action.upper()})

    def _fallback_memory_decision(
        self,
        *,
        user_message: Message,
        intent: IntentSignal,
        conversation_state: ConversationStateSignal,
        relevant_memories: list[MemoryRecord],
    ) -> MemoryDecision:
        content = user_message.content.strip()
        lowered = content.lower()
        if re.search(r"\b(?:forget|delete|remove)\b", lowered):
            target = relevant_memories[0].id if relevant_memories else None
            return MemoryDecision(
                action="DELETE" if target else "NOOP",
                target_memory_id=target,
                reason="The learner asked to forget related memory.",
            )

        if not is_essential_learning_text(content) and conversation_state.state not in {
            "confused",
            "understanding",
        }:
            return MemoryDecision(
                action="NOOP",
                reason="The message is not durable educational memory.",
            )

        category = self._fallback_category(content, conversation_state)
        existing = self._matching_memory(category, content, relevant_memories)
        return MemoryDecision(
            action="UPDATE" if existing else "ADD",
            category=category,
            memory=self._memory_text_for_category(content, category, intent),
            target_memory_id=existing.id if existing else None,
            reason="Durable learner state detected.",
        )

    def _extract_student_memory(
        self,
        *,
        raw_memory: str,
        category: str | None,
        user_message: Message,
        intent: IntentSignal,
    ) -> StudentMemoryObject:
        """Convert one durable turn into a structured student memory object."""

        topic = self._topic_from_intent_or_text(intent) or self._canonical_topic(raw_memory)
        category_key = self._normalize_category(category)
        concepts = self._concepts_from_text(" ".join([raw_memory, intent.raw_text, topic or ""]))
        difficulty = self._difficulty_from_text(raw_memory, category_key)
        progress = self._progress_from_category(raw_memory, category_key)
        important_facts = self._important_facts_from_memory(raw_memory, category_key)
        tags = self._tags_for_memory(
            topic=topic,
            concepts=concepts,
            category=category_key,
        )
        return StudentMemoryObject(
            topic=topic,
            concepts=concepts,
            difficulty=difficulty,
            progress=progress,
            important_facts=important_facts,
            tags=tags,
            timestamp=user_message.timestamp,
        )

    def _target_memory_for_evolution(
        self,
        *,
        action: str,
        decision: MemoryDecision,
        new_memory: StudentMemoryObject,
        relevant_memories: list[MemoryRecord],
    ) -> MemoryRecord | None:
        if action == "UPDATE" and decision.target_memory_id:
            return next(
                (
                    memory
                    for memory in relevant_memories
                    if memory.id == decision.target_memory_id
                ),
                None,
            )
        if action != "ADD":
            return None

        new_terms = self._student_memory_terms(new_memory)
        category_key = self._normalize_category(decision.category)
        for memory in relevant_memories:
            if not self._categories_can_evolve(
                category_key,
                self._normalize_category(memory.type),
            ):
                continue
            existing = self._student_memory_from_record(memory)
            existing_terms = self._student_memory_terms(existing)
            if self._same_learning_area(new_memory, existing, new_terms, existing_terms):
                return memory
        return None

    def _evolve_student_memory(
        self,
        *,
        existing: MemoryRecord,
        new_memory: StudentMemoryObject,
    ) -> StudentMemoryObject:
        """Merge old and new student notes while keeping the newest progress."""

        old_memory = self._student_memory_from_record(existing)
        return StudentMemoryObject(
            topic=new_memory.topic or old_memory.topic,
            concepts=self._append_unique(old_memory.concepts, new_memory.concepts)[-8:],
            difficulty=self._evolved_text(old_memory.difficulty, new_memory.difficulty),
            progress=new_memory.progress or old_memory.progress,
            important_facts=self._append_unique(
                old_memory.important_facts,
                new_memory.important_facts,
            )[-8:],
            tags=self._append_unique(old_memory.tags, new_memory.tags)[-10:],
            timestamp=new_memory.timestamp,
        )

    def _student_memory_from_record(self, memory: MemoryRecord) -> StudentMemoryObject:
        try:
            return StudentMemoryObject.model_validate_json(memory.memory)
        except ValueError:
            return StudentMemoryObject(
                topic=memory.topic,
                concepts=self._concepts_from_text(memory.memory),
                difficulty=self._difficulty_from_text(
                    memory.memory,
                    self._normalize_category(memory.type),
                ),
                progress=self._progress_from_category(
                    memory.memory,
                    self._normalize_category(memory.type),
                ),
                important_facts=self._important_facts_from_memory(
                    memory.memory,
                    self._normalize_category(memory.type),
                ),
                tags=self._tags_for_memory(
                    topic=memory.topic,
                    concepts=self._concepts_from_text(memory.memory),
                    category=self._normalize_category(memory.type),
                ),
                timestamp=memory.timestamp,
            )

    def _log_evolved_memories(
        self,
        user_id: str,
        memories: list[MemoryRecord],
    ) -> None:
        """Print the current user's evolved student memories after each turn."""

        logger.warning(
            "[EVOLVED MEMORY DEBUG] user_id=%s active_memory_count=%s",
            user_id,
            len(memories),
        )
        if not memories:
            logger.warning("[EVOLVED MEMORY DEBUG] no active evolved memories")
            return
        for index, memory in enumerate(memories, start=1):
            structured = self._student_memory_from_record(memory)
            logger.warning(
                "[EVOLVED MEMORY DEBUG] %s id=%s type=%s topic=%s concepts=%s difficulty=%s progress=%s facts=%s tags=%s",
                index,
                memory.id,
                memory.type,
                structured.topic or memory.topic or "",
                structured.concepts,
                structured.difficulty or "",
                structured.progress or "",
                structured.important_facts,
                structured.tags,
            )

    def _profile_from_memories(
        self,
        user_id: str,
        memories: list[MemoryRecord],
    ) -> LearnerProfile:
        goals: list[str] = []
        completed: list[str] = []
        current: list[str] = []
        interests: list[str] = []
        mistakes: list[str] = []
        style: str | None = None
        projects: list[str] = []

        for memory in memories:
            topic = memory.topic
            student_memory = self._student_memory_from_record(memory)
            text = self._memory_summary_text(memory).lower()
            category = self._normalize_category(memory.type)
            if category == "goal":
                goals = self._append_unique(goals, student_memory.important_facts or [text])
            if topic and category in {"knowledge_state", "fact", "goal"}:
                current = self._append_unique(current, [topic])
                interests = self._append_unique(interests, [topic])
            if topic and category == "achievement":
                completed = self._append_unique(completed, [topic])
                interests = self._append_unique(interests, [topic])
                projects = self._append_unique(
                    projects,
                    student_memory.important_facts or [self._memory_summary_text(memory)],
                )
            if topic and category == "learning_difficulty":
                mistakes = self._append_unique(mistakes, [topic])
            if category == "preference" or "hands-on" in text or "coding example" in text:
                style = "hands-on implementation"

        return LearnerProfile(
            user_id=user_id,
            learning_goals=goals[-10:],
            completed_topics=completed[-20:],
            current_topics=current[-6:],
            preferred_explanation_style=style,
            previous_mistakes=mistakes[-10:],
            ongoing_projects=projects[-10:],
            interests=interests[-10:],
        )

    @classmethod
    def _memory_summary_text(cls, memory: MemoryRecord) -> str:
        try:
            structured = StudentMemoryObject.model_validate_json(memory.memory)
        except ValueError:
            return memory.memory
        parts = [
            f"topic: {structured.topic}" if structured.topic else "",
            f"concepts: {', '.join(structured.concepts)}" if structured.concepts else "",
            f"difficulty: {structured.difficulty}" if structured.difficulty else "",
            f"progress: {structured.progress}" if structured.progress else "",
            (
                f"facts: {'; '.join(structured.important_facts)}"
                if structured.important_facts
                else ""
            ),
        ]
        return "; ".join(part for part in parts if part)

    @classmethod
    def _concepts_from_text(cls, text: str) -> list[str]:
        """Extract compact concept tags without needing a separate DB schema."""

        concepts = cls._topics_from_text_static(text)
        phrase_patterns = (
            r"\bbase cases?\b",
            r"\bcall stack\b",
            r"\brecursive functions?\b",
            r"\binner joins?\b",
            r"\bouter joins?\b",
            r"\bprocess scheduling\b",
            r"\btime complexity\b",
            r"\bbinary search tree\b",
            r"\blinked lists?\b",
        )
        for pattern in phrase_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                concepts.append(cls._title_concept(match.group(0)))
        ignored_concepts = {
            "Achievement",
            "Fact",
            "Goal",
            "Knowledge",
            "Learning",
            "Preference",
            "Student",
            "User",
        }
        for token in re.findall(r"\b[A-Z][A-Za-z0-9+#.]{2,}\b|\b[A-Z]{2,}\b", text):
            concept = cls._title_concept(token)
            if concept not in ignored_concepts:
                concepts.append(concept)
        return cls._append_unique([], concepts)[:8]

    @staticmethod
    def _difficulty_from_text(raw_memory: str, category_key: str) -> str | None:
        if category_key == "learning_difficulty":
            return raw_memory
        match = re.search(
            r"\b(?:confused about|stuck on|struggle(?:s)? with|weak (?:at|in)|difficulty with)\s+(.+)",
            raw_memory,
            re.I,
        )
        if match:
            return match.group(0).strip()
        return None

    @staticmethod
    def _progress_from_category(raw_memory: str, category_key: str) -> str | None:
        if category_key == "achievement":
            return raw_memory
        if category_key == "knowledge_state":
            return raw_memory
        if category_key == "learning_difficulty":
            return "needs practice and prerequisite repair"
        if category_key == "goal":
            return "active learning goal"
        if category_key == "preference":
            return "preferred tutoring style noted"
        return None

    @staticmethod
    def _important_facts_from_memory(raw_memory: str, category_key: str) -> list[str]:
        if category_key in {"goal", "preference", "achievement", "fact"}:
            return [raw_memory]
        return []

    @classmethod
    def _tags_for_memory(
        cls,
        *,
        topic: str | None,
        concepts: list[str],
        category: str,
    ) -> list[str]:
        tags = [category.replace("_", " ").title()]
        if topic:
            tags.append(topic)
        tags.extend(concepts)
        return cls._append_unique([], tags)[:10]

    @classmethod
    def _student_memory_terms(cls, memory: StudentMemoryObject) -> set[str]:
        return cls._memory_match_terms(
            " ".join(
                [
                    memory.topic or "",
                    " ".join(memory.concepts),
                    " ".join(memory.tags),
                    memory.difficulty or "",
                    memory.progress or "",
                    " ".join(memory.important_facts),
                ]
            )
        )

    @staticmethod
    def _same_learning_area(
        new_memory: StudentMemoryObject,
        existing: StudentMemoryObject,
        new_terms: set[str],
        existing_terms: set[str],
    ) -> bool:
        if new_memory.topic and existing.topic:
            if new_memory.topic.lower() == existing.topic.lower():
                return True
        overlap = new_terms & existing_terms
        return len(overlap) >= 2

    @staticmethod
    def _categories_can_evolve(new_category: str, existing_category: str) -> bool:
        if new_category == existing_category:
            return True
        learning_state_categories = {
            "knowledge_state",
            "learning_difficulty",
            "achievement",
        }
        return (
            new_category in learning_state_categories
            and existing_category in learning_state_categories
        )

    @staticmethod
    def _evolved_text(old: str | None, new: str | None) -> str | None:
        if not old:
            return new
        if not new or new.lower() == old.lower():
            return old
        return f"{old}; {new}"

    @staticmethod
    def _prompt_memories(
        *,
        retrieved: list[RetrievedMemory],
        all_memories: list[MemoryRecord],
        current_message_id: str,
        limit: int = 3,
    ) -> list[RetrievedMemory]:
        del all_memories
        filtered = [
            item
            for item in retrieved
            if item.record.source_message_id != current_message_id
        ]
        return sorted(
            filtered,
            key=lambda item: (item.total_score, item.record.timestamp),
            reverse=True,
        )[:limit]

    @staticmethod
    def _unique_memories(*memory_groups: list[MemoryRecord]) -> list[MemoryRecord]:
        unique: dict[str, MemoryRecord] = {}
        for memories in memory_groups:
            for memory in memories:
                unique[memory.id] = memory
        return list(unique.values())

    @staticmethod
    def _memory_decision_prompt() -> str:
        return (
            "You are a memory management system for an educational tutor.\n\n"
            "Your task is to decide how to update a user's long-term memory based on:\n"
            "1. Existing memories\n"
            "2. New conversation information\n\n"
            "You have four possible actions:\n\n"
            "ADD:\n"
            "Use when the new information introduces durable learner information that "
            "does not exist in memory.\n\n"
            "UPDATE:\n"
            "Use when the new information modifies, corrects, or replaces an existing "
            "memory.\n\n"
            "DELETE:\n"
            "Use when an existing memory is no longer valid or the user explicitly "
            "removes it.\n\n"
            "NOOP:\n"
            "Use when the new information does not provide useful long-term memory or "
            "does not change existing knowledge.\n\n"
            "Memory categories:\n"
            "- Goal\n"
            "- Knowledge State\n"
            "- Learning Difficulty\n"
            "- Preference\n"
            "- Achievement\n"
            "- Fact\n\n"
            "Rules:\n"
            "- Do not store temporary emotions, one-time requests, greetings, or irrelevant conversation details.\n"
            "- Prefer updating an existing memory rather than creating duplicates.\n"
            "- If new information contradicts old information, update the old memory with the latest user-provided information.\n"
            "- Preserve important historical information when it is still relevant.\n"
            "- Do not make assumptions beyond what the user explicitly stated.\n"
            "- For NOOP, set category, memory, and target_memory_id to null.\n"
            "- For ADD, set target_memory_id to null.\n"
            "- For UPDATE or DELETE, set target_memory_id to the affected existing memory id.\n"
            "- Return ONLY valid JSON.\n\n"
            "Existing memories are provided in the user message as existing_memories.\n"
            "New conversation information is provided in the user message as user_message.\n\n"
            "Return this JSON shape only:\n\n"
            "{\n"
            '  "action": "ADD | UPDATE | DELETE | NOOP",\n'
            '  "category": "Goal | Knowledge State | Learning Difficulty | Preference | Achievement | Fact | null",\n'
            '  "memory": "updated memory text if applicable",\n'
            '  "target_memory_id": "id of affected memory if applicable",\n'
            '  "reason": "brief explanation"\n'
            "}"
        )

    @staticmethod
    def _json_object(text: str) -> str:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM did not return a JSON object.")
        return text[start : end + 1]

    def _fallback_category(
        self,
        content: str,
        conversation_state: ConversationStateSignal,
    ) -> str:
        lowered = content.lower()
        if re.search(r"\b(?:goal|want to learn|want to master|want to become|preparing for|dream)\b", lowered):
            return "Goal"
        if re.search(r"\b(?:prefer|like examples|learn best|hands-on|implementation)\b", lowered):
            return "Preference"
        if re.search(r"\b(?:confused|stuck|weak at|struggle|mistake|don't understand|do not understand)\b", lowered):
            return "Learning Difficulty"
        if re.search(r"\b(?:mastered|comfortable with|strong at)\b", lowered):
            return "Knowledge State"
        if re.search(r"\b(?:built|implemented|completed|finished|solved|learned)\b", lowered):
            return "Achievement"
        if conversation_state.state == "understanding":
            return "Knowledge State"
        if re.search(r"\b(?:what is|whats|where is|capital|is it in|live|lives|from)\b", lowered):
            return "Fact"
        return "Knowledge State"

    def _memory_text_for_category(
        self,
        content: str,
        category: str,
        intent: IntentSignal,
    ) -> str:
        normalized = " ".join(content.strip().split())
        category_key = self._normalize_category(category)
        if category_key == "goal":
            return f"Student goal: {normalized}"
        if category_key == "preference":
            return f"Learning preference: {normalized}"
        if category_key == "learning_difficulty":
            return f"Learning difficulty: {normalized}"
        if category_key == "achievement":
            return f"Achievement: {normalized}"
        if category_key == "fact":
            return f"Fact discussed: {normalized}"
        return f"Knowledge state: {normalized or intent.raw_text}"

    def _matching_memory(
        self,
        category: str,
        content: str,
        memories: list[MemoryRecord],
    ) -> MemoryRecord | None:
        topic_terms = self._memory_match_terms(content)
        category_key = self._normalize_category(category)
        for memory in memories:
            if self._normalize_category(memory.type) != category_key:
                continue
            memory_terms = self._memory_match_terms(memory.memory)
            if topic_terms and topic_terms & memory_terms:
                return memory
        return None

    @staticmethod
    def _memory_match_terms(text: str) -> set[str]:
        stopwords = {
            "a",
            "about",
            "am",
            "and",
            "as",
            "for",
            "i",
            "in",
            "is",
            "learning",
            "prefer",
            "preference",
            "student",
            "the",
            "to",
            "want",
        }
        return {
            token
            for token in re.sub(r"[^a-z0-9+# ]+", " ", text.lower()).split()
            if len(token) > 2 and token not in stopwords
        }

    @staticmethod
    def _normalize_category(category: str | None) -> str:
        normalized = (category or "Fact").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "goal": "goal",
            "knowledge_state": "knowledge_state",
            "learning_difficulty": "learning_difficulty",
            "difficulty": "learning_difficulty",
            "preference": "preference",
            "achievement": "achievement",
            "fact": "fact",
            "learning_event": "knowledge_state",
            "strong_topic": "knowledge_state",
            "completed_topic": "achievement",
            "weak_topic": "learning_difficulty",
            "study_plan": "goal",
        }
        return aliases.get(normalized, "fact")

    def _importance_for_category(self, category: str | None) -> int:
        return {
            "goal": 10,
            "learning_difficulty": 9,
            "preference": 8,
            "achievement": 9,
            "knowledge_state": 7,
            "fact": 6,
        }.get(self._normalize_category(category), 6)

    def _retrieval_query(
        self,
        intent: IntentSignal,
        conversation_state: ConversationStateSignal,
    ) -> str:
        return " ".join(
            item
            for item in [
                intent.raw_text,
                intent.topic or "",
                conversation_state.state,
            ]
            if item
        )

    @staticmethod
    def _retrieval_mode(text: str) -> str:
        lowered = text.lower().strip()
        if (
            re.search(r"\bwhat\b.*\b(?:discuss(?:ed)?|talk(?:ed)? about|cover(?:ed)?|learn(?:ed)?)\b", lowered)
            or re.search(r"\b(?:topics?|concepts?)\b.*\b(?:we|our|us)\b.*\b(?:discussed|covered|learned|talked about)\b", lowered)
            or re.search(r"\b(?:continue|resume|carry on|go back to|pick up)\b.*\b(?:earlier|previous|last|where we left|what we discussed)\b", lowered)
            or re.search(r"\b(?:can we|could we|lets|let's)\b.*\bcontinue\b.*\b(?:discussed|earlier|previous)\b", lowered)
        ):
            return "CURRENT_CONVERSATION"
        if (
            re.search(r"\b(?:about me|profile)\b", lowered)
            or re.search(r"\bwhat\b.*\b(?:remember|know|learned)\b.*\bme\b", lowered)
            or re.search(r"\bwhat\b.*\b(?:goals?|preferences?|learning style)\b", lowered)
            or re.search(r"\b(?:my goals?|my preferences?|my learning style)\b", lowered)
        ):
            return "USER_PROFILE"
        if re.search(r"\b(?:explain|teach|describe)\b", lowered) or re.search(r"^what\s+is\b", lowered):
            return "KNOWLEDGE"
        return "GENERAL"

    @staticmethod
    def _safe_summary(text: str, max_chars: int = 120) -> str:
        compact = " ".join(text.strip().split())
        if len(compact) <= max_chars:
            return compact
        return f"{compact[: max_chars - 1].rstrip()}..."

    def _topic_from_intent_or_text(self, intent: IntentSignal) -> str | None:
        if intent.topic:
            return self._canonical_topic(intent.topic)
        return self._canonical_topic(intent.raw_text)

    def _canonical_topic(self, text: str) -> str | None:
        topics = self._topics_from_text(text)
        return topics[-1] if topics else text.strip()[:80] or None

    def _topics_from_text(self, text: str) -> list[str]:
        return self._topics_from_text_static(text)

    @classmethod
    def _topics_from_text_static(cls, text: str) -> list[str]:
        lowered = text.lower()
        return [
            canonical
            for alias, canonical in cls._known_topic_aliases.items()
            if re.search(rf"\b{re.escape(alias)}\b", lowered)
        ]

    @staticmethod
    def _title_concept(text: str) -> str:
        acronyms = {"dfs", "bfs", "bst", "rag", "api", "sql", "dsa", "os"}
        words = text.strip().split()
        normalized_words = [
            word.upper() if word.lower() in acronyms else word.capitalize()
            for word in words
        ]
        return " ".join(normalized_words)

    @staticmethod
    def _append_unique(current: list[str], items: list[str]) -> list[str]:
        result = [item for item in current if item]
        seen = {item.lower() for item in result}
        for item in items:
            normalized = item.strip()
            if normalized and normalized.lower() not in seen:
                result.append(normalized)
                seen.add(normalized.lower())
        return result
