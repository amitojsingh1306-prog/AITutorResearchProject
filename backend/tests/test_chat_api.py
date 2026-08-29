"""End-to-end API tests using an isolated persistent ChromaDB."""

from collections.abc import Iterator
from contextlib import contextmanager
import json
from pathlib import Path
import re

from fastapi.testclient import TestClient

from backend.agents.conversation_state_agent import ConversationStateAgent
from backend.agents.dialogue_manager_agent import DialogueManagerAgent
from backend.agents.intent_agent import IntentAgent
from backend.agents.response_generation_agent import ResponseGenerationAgent
from backend.config import Settings
from backend.database.chroma_repository import ChromaChatRepository
from backend.llm.ollama_client import OllamaClientError
from backend.main import create_app
from backend.models.chat import ChatCreateRequest, ChatMessageRequest, Message
from backend.models.learner import MemoryRecord, TeachingPlan
from backend.memory.memory_store import ChromaVectorMemoryStore
from backend.memory.retrieval import VectorMemoryRetriever
from backend.orchestration.tutor_orchestrator import TutorOrchestrator
from backend.services.chat_service import ChatService
from backend.utils.time import utc_now


class MemoryRenderingLlmClient:
    """Small deterministic final renderer for API tests.

    Memory decisions intentionally return invalid JSON so MemoryManager uses
    the production fallback classifier. Final replies still pass through this
    fake LLM, which keeps tests aligned with the real request pipeline.
    """

    system_prompts: list[str]

    def __init__(self) -> None:
        self.system_prompts = []

    def generate_text(self, *args: object, **kwargs: object) -> str:
        user_content = str(kwargs.get("user_content", ""))
        if "Return ONLY a JSON array of 4-6 teaching headings." in user_content:
            return '["Definition","Working","Example","Complexity","Applications"]'
        return "not-json"

    def generate_reply(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> str:
        prompt = system_prompt or ""
        self.system_prompts.append(prompt)
        user_content = messages[-1].content if messages else ""
        lowered = user_content.lower()

        if "memory_history_request: durable_user_memory" in prompt:
            return (
                "Here is what I remember about you:\n"
                "Goals\n"
                "- I am preparing for GATE CSE and my dream is IISc\n"
                "Preferences\n"
                "- I prefer Python over Java\n"
                "- I prefer study routines as tables\n"
                "Knowledge\n"
                "- I mastered Linked Lists\n"
                "Learning Difficulties\n"
                "- I struggle with Dynamic Programming\n"
                "Profile / Facts\n"
                "- I live in Bangalore"
            )

        if "memory_history_request: first_permanent_memory" in prompt:
            if "status: no permanent learning memory stored" in prompt:
                return "I do not have a first permanent learning memory stored yet."
            return (
                "Your first permanent learning memory was: "
                "I want to learn calculus."
            )

        if "memory_history_request: conversation_summary" in prompt:
            if (
                "status: only short casual turns found" in prompt
                or "status: no meaningful prior learning topic found" in prompt
            ):
                return "I do not remember an earlier learning discussion yet."
            lines = [
                line.removeprefix("learning_turn: ")
                for line in prompt.splitlines()
                if line.startswith("learning_turn: ")
            ]
            return (
                "Here is what I remember from our earlier learning:\n"
                "Earlier learning topics\n"
                + "\n".join(f"- {line}" for line in lines)
            )

        if "memory_history_request: resume_previous_topic" in prompt:
            latest = self._field(prompt, "latest_topic")
            if latest:
                return (
                    f"Yes, let's continue from {latest}. "
                    "quick recap: tell me if you want recap, depth, or practice."
                )
            return "I do not remember a solid learning topic to continue yet."

        if "memory_history_request: list_discussed_topics" in prompt:
            topics = [
                line.removeprefix("topic: ")
                for line in prompt.splitlines()
                if line.startswith("topic: ")
            ]
            if not topics:
                return "I do not have any learning topics to list yet."
            return "\n".join(f"- {topic}" for topic in topics)

        if "memory_history_request: targeted_history_lookup" in prompt:
            if "status: no matching prior discussion found" in prompt:
                query = self._field(prompt, "query_terms") or "that"
                return f"I do not remember us discussing {query} earlier."
            matches = [
                line.removeprefix("match: ")
                for line in prompt.splitlines()
                if line.startswith("match: ")
            ]
            return "Yes, I remember something related:\n" + "\n".join(
                f"- {match}" for match in matches
            )

        if "stategraph" in lowered or "StateGraph" in prompt:
            return "StateGraph connects with Nodes and Edges."
        if lowered:
            return f"Here is a concise answer about {user_content}."
        return "Here is a concise answer."

    def stream_reply(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> Iterator[str]:
        reply = self.generate_reply(messages, system_prompt)
        for index in range(0, len(reply), 8):
            yield reply[index : index + 8]

    @staticmethod
    def _field(prompt: str, name: str) -> str | None:
        match = re.search(rf"^{re.escape(name)}: (.+)$", prompt, re.MULTILINE)
        return match.group(1) if match else None


@contextmanager
def build_client(
    database_path: Path,
    llm_client: object | None = None,
) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        chroma_path=database_path,
        groq_api_key=None,
        ollama_base_url=None,
    )
    with TestClient(create_app(settings)) as client:
        if llm_client is not None:
            service = client.app.state.chat_service
            client.app.state.chat_service = ChatService(
                service._repository,  # type: ignore[attr-defined]
                llm_client,  # type: ignore[arg-type]
                working_memory_limit=settings.working_memory_message_limit,
            )
        yield client


def parse_sse_events(body: str) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    for block in body.strip().split("\n\n"):
        event = ""
        data = ""
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = line.removeprefix("data: ")
        if event:
            events.append((event, data))
    return events


def test_chat_lifecycle_is_persisted(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        headers = {"X-User-Id": "student-a@example.com"}
        create_response = client.post("/chat/create", json={}, headers=headers)
        assert create_response.status_code == 201
        chat = create_response.json()
        assert chat["user_id"] == "student-a@example.com"

        message_response = client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "Explain hybrid memory systems"},
            headers=headers,
        )
        assert message_response.status_code == 201
        message_payload = message_response.json()
        assert "hybrid memory systems" in message_payload["assistant_message"]["content"]
        assert message_payload["user_message"]["role"] == "user"
        assert message_payload["assistant_message"]["role"] == "assistant"

        detail_response = client.get(f"/chat/{chat['id']}", headers=headers)
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert len(detail["messages"]) == 2
        assert detail["messages"][0]["content"] == "Explain hybrid memory systems"

        list_response = client.get("/chat/list", headers=headers)
        assert list_response.status_code == 200
        assert list_response.json()[0]["id"] == chat["id"]


def test_streaming_chat_flow_saves_final_assistant_message_once(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        headers = {"X-User-Id": "student-a@example.com"}
        chat = client.post("/chat/create", json={}, headers=headers).json()

        with client.stream(
            "POST",
            f"/chat/{chat['id']}/message/stream",
            json={"content": "Explain hybrid memory systems"},
            headers=headers,
        ) as response:
            assert response.status_code == 200
            body = response.read().decode("utf-8")

        events = parse_sse_events(body)
        event_names = [event for event, _data in events]
        assert event_names.count("user_message") == 1
        assert event_names.count("assistant_message_start") == 1
        assert event_names.count("done") == 1
        assert "chunk" in event_names

        repository = ChromaChatRepository(tmp_path / "chroma")
        messages = repository.list_messages(chat["id"], "student-a@example.com")
        assistant_messages = [
            message for message in messages if message.role == "assistant"
        ]
        assert len(messages) == 2
        assert len(assistant_messages) == 1
        assert assistant_messages[0].content
        assert "hybrid memory systems" in assistant_messages[0].content


def test_streaming_error_does_not_save_empty_assistant_message(tmp_path: Path) -> None:
    class FailingStreamClient:
        def generate_text(self, *args: object, **kwargs: object) -> str:
            raise OllamaClientError("memory decision failed")

        def stream_reply(self, *args: object, **kwargs: object):
            raise OllamaClientError("stream failed")
            yield ""

    repository = ChromaChatRepository(tmp_path / "chroma")
    service = ChatService(repository, FailingStreamClient())  # type: ignore[arg-type]
    chat = service.create_chat(ChatCreateRequest(), "student-a@example.com")

    events = list(
        service.stream_message(
            chat.id,
            ChatMessageRequest(content="Explain binary search trees"),
            "student-a@example.com",
        )
    )

    assert any("event: error" in event for event in events)
    messages = repository.list_messages(chat.id, "student-a@example.com")
    assert len(messages) == 1
    assert messages[0].role == "user"


def test_missing_chat_returns_404(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        response = client.get(
            "/chat/does-not-exist",
            headers={"X-User-Id": "student-a@example.com"},
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Chat not found."}


def test_chat_history_is_filtered_by_user(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        user_a = {"X-User-Id": "student-a@example.com"}
        user_b = {"X-User-Id": "student-b@example.com"}

        chat_a = client.post("/chat/create", json={}, headers=user_a).json()
        chat_b = client.post("/chat/create", json={}, headers=user_b).json()

        list_a = client.get("/chat/list", headers=user_a)
        list_b = client.get("/chat/list", headers=user_b)

        assert [chat["id"] for chat in list_a.json()] == [chat_a["id"]]
        assert [chat["id"] for chat in list_b.json()] == [chat_b["id"]]

        cross_user_response = client.get(f"/chat/{chat_b['id']}", headers=user_a)
        assert cross_user_response.status_code == 404


def test_long_term_learning_memory_influences_future_turns(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma", MemoryRenderingLlmClient()) as client:
        headers = {"X-User-Id": "student-a@example.com"}

        first_chat = client.post("/chat/create", json={}, headers=headers).json()
        client.post(
            f"/chat/{first_chat['id']}/message",
            json={"content": "I am learning LangGraph"},
            headers=headers,
        )
        client.post(
            f"/chat/{first_chat['id']}/message",
            json={"content": "I learned Nodes and Edges"},
            headers=headers,
        )

        second_chat = client.post("/chat/create", json={}, headers=headers).json()
        response = client.post(
            f"/chat/{second_chat['id']}/message",
            json={"content": "Explain StateGraph"},
            headers=headers,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert "Nodes" in assistant_reply
        assert "Edges" in assistant_reply
        assert "StateGraph" in assistant_reply


def test_social_turns_get_short_dialogue_controls() -> None:
    intent = IntentAgent().analyze("Wow thank you so much")
    state = ConversationStateAgent().classify(intent)
    dialogue = DialogueManagerAgent().calibrate(
        intent=intent,
        conversation_state=state,
        plan=TeachingPlan(
            mode="acknowledge",
            review=False,
            depth="beginner",
            steps=[],
            next_action="stop",
            tone="warm",
        ),
    )

    assert state.state == "gratitude"
    assert dialogue.conversation_type == "gratitude"
    assert dialogue.length == "short"
    assert dialogue.stop_after_acknowledgement is True


def test_progression_and_topic_words_are_not_confused() -> None:
    intent_agent = IntentAgent()
    state_agent = ConversationStateAgent()

    progression = state_agent.classify(intent_agent.analyze("What's next?"))
    next_js_question = state_agent.classify(intent_agent.analyze("Explain Next.js routing"))

    assert progression.state == "progression"
    assert next_js_question.state == "continuation"


def test_gratitude_api_reply_stays_brief(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        headers = {"X-User-Id": "student-a@example.com"}
        chat = client.post("/chat/create", json={}, headers=headers).json()

        response = client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "wow ty for teaching me"},
            headers=headers,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert assistant_reply == "Happy to help. Glad it clicked."
        assert "Keep Exploring" not in assistant_reply
        assert len(assistant_reply.split()) <= 8


def test_social_turns_are_not_promoted_to_long_term_memory(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        headers = {"X-User-Id": "student-a@example.com"}
        chat = client.post("/chat/create", json={}, headers=headers).json()

        response = client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "thanks"},
            headers=headers,
        )

        assert response.status_code == 201
        repository = ChromaChatRepository(tmp_path / "chroma")
        assert repository.list_memories("student-a@example.com") == []


def test_mem0_style_memory_categories_and_operations(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        headers = {"X-User-Id": "student-a@example.com"}
        chat = client.post("/chat/create", json={}, headers=headers).json()

        client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "I want to learn calculus"},
            headers=headers,
        )
        repository = ChromaChatRepository(tmp_path / "chroma")
        memories = repository.list_memories("student-a@example.com")
        assert len(memories) == 1
        assert memories[0].type == "goal"

        client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "I want to learn calculus deeply"},
            headers=headers,
        )
        memories = repository.list_memories("student-a@example.com")
        assert len(memories) == 1
        assert memories[0].type == "goal"
        assert "deeply" in memories[0].memory

        for content in [
            "I am confused about derivatives",
            "I prefer hands-on coding examples",
            "I completed matrix multiplication",
            "china capital",
        ]:
            client.post(
                f"/chat/{chat['id']}/message",
                json={"content": content},
                headers=headers,
            )

        memory_types = {
            memory.type for memory in repository.list_memories("student-a@example.com")
        }
        assert {
            "goal",
            "learning_difficulty",
            "preference",
            "achievement",
            "fact",
        }.issubset(memory_types)

        client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "forget calculus"},
            headers=headers,
        )
        memories = repository.list_memories("student-a@example.com")
        assert all("calculus" not in memory.memory.lower() for memory in memories)


def test_student_memories_are_structured_and_evolve_by_topic(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        headers = {"X-User-Id": "student-a@example.com"}
        chat = client.post("/chat/create", json={}, headers=headers).json()

        client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "I am confused about SQL joins"},
            headers=headers,
        )
        client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "I learned inner joins"},
            headers=headers,
        )

        repository = ChromaChatRepository(tmp_path / "chroma")
        memories = repository.list_memories("student-a@example.com")
        assert len(memories) == 1
        assert memories[0].topic == "SQL Joins"
        stored_memory = json.loads(memories[0].memory)
        assert stored_memory["topic"] == "SQL Joins"
        assert "SQL Joins" in stored_memory["tags"]
        assert "inner joins" in stored_memory["progress"].lower()
        assert "confused about SQL joins" in stored_memory["difficulty"]


def test_recursion_memory_debug_shows_evolution_without_duplicates(
    tmp_path: Path,
    caplog,
) -> None:
    with build_client(tmp_path / "chroma") as client:
        headers = {"X-User-Id": "student-a@example.com"}
        chat = client.post("/chat/create", json={}, headers=headers).json()

        client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "I am confused about recursion base cases"},
            headers=headers,
        )
        client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "I understood recursion examples but need practice"},
            headers=headers,
        )

        repository = ChromaChatRepository(tmp_path / "chroma")
        recursion_memories = [
            memory
            for memory in repository.list_memories("student-a@example.com")
            if memory.topic == "Recursion"
        ]
        assert len(recursion_memories) == 1
        stored_memory = json.loads(recursion_memories[0].memory)
        assert stored_memory["topic"] == "Recursion"
        assert "confused about recursion base cases" in stored_memory["difficulty"]
        assert "understood recursion examples" in stored_memory["progress"].lower()
        assert "[EVOLVED MEMORY DEBUG]" in caplog.text
        assert "topic=Recursion" in caplog.text


def test_about_me_question_uses_durable_memory_not_transcript(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma", MemoryRenderingLlmClient()) as client:
        headers = {"X-User-Id": "student-a@example.com"}
        chat = client.post("/chat/create", json={}, headers=headers).json()

        for content in [
            "I am preparing for GATE CSE and my dream is IISc",
            "I prefer Python over Java",
            "I prefer study routines as tables",
            "I mastered Linked Lists",
            "I struggle with Dynamic Programming",
            "I live in Bangalore",
        ]:
            client.post(
                f"/chat/{chat['id']}/message",
                json={"content": content},
                headers=headers,
            )

        # Transcript-only noise should not be quoted in the about-me memory answer.
        client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "tell me a sentence about rain"},
            headers=headers,
        )

        response = client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "What do you remember about me?"},
            headers=headers,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert "Here is what I remember about you" in assistant_reply
        assert "Goals" in assistant_reply
        assert "GATE CSE" in assistant_reply
        assert "IISc" in assistant_reply
        assert "Preferences" in assistant_reply
        assert "Python over Java" in assistant_reply
        assert "study routines as tables" in assistant_reply
        assert "Knowledge" in assistant_reply
        assert "mastered Linked Lists" in assistant_reply
        assert "Learning Difficulties" in assistant_reply
        assert "Dynamic Programming" in assistant_reply
        assert "Profile / Facts" in assistant_reply
        assert "Bangalore" in assistant_reply
        assert "Tutor:" not in assistant_reply
        assert "rain" not in assistant_reply.lower()
        assert "UTC" not in assistant_reply


def test_working_memory_keeps_only_recent_conversation_messages(tmp_path: Path) -> None:
    repository = ChromaChatRepository(tmp_path / "chroma")
    orchestrator = TutorOrchestrator(repository)

    messages = [
        Message(
            id=f"message-{index}",
            chat_id="chat-a",
            user_id="student-a@example.com",
            role="user",
            content=f"Explain topic {index}",
            timestamp=utc_now(),
            session_id="session-a",
        )
        for index in range(12)
    ]
    for message in messages:
        repository.save_message(message)

    orchestrator.generate_reply(
        "chat-a",
        messages[-1],
    )

    assert orchestrator._last_context is not None
    working_messages = orchestrator._last_context.memory.working_messages
    assert len(working_messages) == 10
    assert working_messages[0].content == "Explain topic 2"
    assert working_messages[-1].content == "Explain topic 11"

    prompt_messages = ResponseGenerationAgent().select_messages(orchestrator._last_context)
    assert len(prompt_messages) == 4
    assert prompt_messages[0].content == "Explain topic 8"
    assert prompt_messages[-1].content == "Explain topic 11"


def test_response_prompt_uses_application_selected_headings(tmp_path: Path) -> None:
    class CapturingLlmClient:
        system_prompt = ""

        def generate_text(self, *args: object, **kwargs: object) -> str:
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompt = str(kwargs["system_prompt"])
            return "Definition\n- DFS is a graph traversal method."

    llm_client = CapturingLlmClient()
    repository = ChromaChatRepository(tmp_path / "chroma")
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    user_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id="student-a@example.com",
        role="user",
        content="Explain DFS",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(user_message)

    orchestrator.generate_reply("chat-a", user_message)

    prompt = llm_client.system_prompt
    assert "Application-selected lesson outline:" in prompt
    assert "1. Definition" in prompt
    assert "2. Working" in prompt
    assert "3. Example" in prompt
    assert "4. Time Complexity" in prompt
    assert "5. Applications" in prompt
    assert "Headings to explain now:\n- Definition\n- Working\n- Example" in prompt
    assert "Headings reserved for later:\n- Time Complexity\n- Applications" in prompt
    assert "Explain ONLY the headings listed under 'Headings to explain now'." in prompt
    assert "Do not rename, merge, reorder, skip, or create additional headings." in prompt


def test_unknown_topic_outline_is_planned_then_limited_to_first_headings(
    tmp_path: Path,
) -> None:
    class PlanningLlmClient:
        system_prompts: list[str] = []

        def generate_text(self, *args: object, **kwargs: object) -> str:
            user_content = str(kwargs["user_content"])
            if "Return ONLY a JSON array of 4-6 teaching headings." in user_content:
                return '["Definition","Structure","Insertion","Search","Deletion","Complexity"]'
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompts.append(str(kwargs["system_prompt"]))
            return "Definition\n- A binary search tree stores ordered data."

    llm_client = PlanningLlmClient()
    repository = ChromaChatRepository(tmp_path / "chroma")
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    user_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id="student-a@example.com",
        role="user",
        content="Explain Binary Search Tree",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(user_message)

    orchestrator.generate_reply("chat-a", user_message)

    prompt = llm_client.system_prompts[-1]
    assert "1. Definition" in prompt
    assert "2. Structure" in prompt
    assert "3. Insertion" in prompt
    assert "4. Search" in prompt
    assert "5. Deletion" in prompt
    assert "6. Complexity" in prompt
    assert "Headings to explain now:\n- Definition\n- Structure\n- Insertion" in prompt
    assert "Headings reserved for later:\n- Search\n- Deletion\n- Complexity" in prompt


def test_continue_uses_stored_remaining_headings(tmp_path: Path) -> None:
    class PlanningLlmClient:
        system_prompts: list[str] = []

        def generate_text(self, *args: object, **kwargs: object) -> str:
            user_content = str(kwargs["user_content"])
            if "Return ONLY a JSON array of 4-6 teaching headings." in user_content:
                return '["Definition","Structure","Insertion","Search","Deletion","Complexity"]'
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompts.append(str(kwargs["system_prompt"]))
            return "ok"

    llm_client = PlanningLlmClient()
    repository = ChromaChatRepository(tmp_path / "chroma")
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    first_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id="student-a@example.com",
        role="user",
        content="Explain Binary Search Tree",
        timestamp=utc_now(),
        session_id="session-a",
    )
    continue_message = Message(
        id="message-b",
        chat_id="chat-a",
        user_id="student-a@example.com",
        role="user",
        content="continue",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(first_message)
    repository.save_message(continue_message)

    orchestrator.generate_reply("chat-a", first_message)
    orchestrator.generate_reply("chat-a", continue_message)

    prompt = llm_client.system_prompts[-1]
    assert "Headings to explain now:\n- Search\n- Deletion\n- Complexity" in prompt
    assert "Headings reserved for later:\n- None." in prompt


def test_coding_mode_bypasses_lesson_planner(tmp_path: Path) -> None:
    class CodingLlmClient:
        system_prompt = ""
        outline_calls = 0

        def generate_text(self, *args: object, **kwargs: object) -> str:
            user_content = str(kwargs["user_content"])
            if "Return ONLY a JSON array of 4-6 teaching headings." in user_content:
                self.outline_calls += 1
                return '["Definition","Code","Explanation","Complexity"]'
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompt = str(kwargs["system_prompt"])
            return "```python\nprint('hi')\n```"

    llm_client = CodingLlmClient()
    repository = ChromaChatRepository(tmp_path / "chroma")
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    user_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id="student-a@example.com",
        role="user",
        content="Implement DFS in Python",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(user_message)

    orchestrator.generate_reply("chat-a", user_message)

    assert llm_client.outline_calls == 0
    assert "Response mode: coding" in llm_client.system_prompt
    assert "Coding mode: do not use lesson headings or the lesson planner." in llm_client.system_prompt
    assert "Headings to explain now:\n- No lesson headings for this turn." in llm_client.system_prompt


def test_normal_chat_mode_does_not_use_lesson_planner_for_factual_prompt(
    tmp_path: Path,
) -> None:
    class NormalLlmClient:
        system_prompt = ""
        outline_calls = 0

        def generate_text(self, *args: object, **kwargs: object) -> str:
            user_content = str(kwargs["user_content"])
            if "Return ONLY a JSON array of 4-6 teaching headings." in user_content:
                self.outline_calls += 1
                return '["Definition","Example","Key Points","Applications"]'
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompt = str(kwargs["system_prompt"])
            return "Beijing."

    llm_client = NormalLlmClient()
    repository = ChromaChatRepository(tmp_path / "chroma")
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    user_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id="student-a@example.com",
        role="user",
        content="china capital",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(user_message)

    orchestrator.generate_reply("chat-a", user_message)

    assert llm_client.outline_calls == 0
    assert "Response mode: qa" in llm_client.system_prompt
    assert "QA mode: do not use lesson planning." in llm_client.system_prompt


def test_memory_retrieval_filters_and_reranks_os_topic_memories(tmp_path: Path) -> None:
    repository = ChromaChatRepository(tmp_path / "chroma")
    user_id = "student-a@example.com"
    for index, (memory, memory_type, topic) in enumerate(
        [
            ("User is preparing for GATE.", "goal", "GATE"),
            ("Explained Binary Search Tree.", "knowledge_state", "BST"),
            ("Explained Operating System process scheduling.", "knowledge_state", "Operating System"),
            ("Explained Depth First Search.", "knowledge_state", "DFS"),
            ("User prefers concise answers.", "preference", None),
        ]
    ):
        repository.save_memory(
            MemoryRecord(
                id=f"memory-{index}",
                user_id=user_id,
                timestamp=utc_now(),
                memory=memory,
                importance=8,
                type=memory_type,
                topic=topic,
                status="active",
            )
        )

    retriever = VectorMemoryRetriever(ChromaVectorMemoryStore(repository))
    memories = retriever.retrieve(
        user_id=user_id,
        query="List the topics covered in Operating System.",
        limit=3,
    )

    memory_texts = [item.record.memory for item in memories]
    assert memory_texts == ["Explained Operating System process scheduling."]


def test_profile_memory_query_filters_out_conversation_events_and_topic_memories(
    tmp_path: Path,
) -> None:
    repository = ChromaChatRepository(tmp_path / "chroma")
    user_id = "student-a@example.com"
    for index, (memory, memory_type, topic) in enumerate(
        [
            ("Fact discussed: User lives in Bangalore.", "fact", "Bangalore"),
            ("Student goal: User wants AIR 1 in GATE CSE.", "goal", "GATE"),
            ("Learning preference: User prefers hands-on learning.", "preference", None),
            ("Knowledge state: User studied Binary Search Tree.", "knowledge_state", "BST"),
            (
                "The user asked about another user's previous request.",
                "conversation_event",
                None,
            ),
        ]
    ):
        repository.save_memory(
            MemoryRecord(
                id=f"memory-{index}",
                user_id=user_id,
                timestamp=utc_now(),
                memory=memory,
                importance=8,
                type=memory_type,
                topic=topic,
                status="active",
            )
        )

    retriever = VectorMemoryRetriever(ChromaVectorMemoryStore(repository))
    memories = retriever.retrieve(
        user_id=user_id,
        query="What do you remember about me?",
        limit=5,
    )

    memory_texts = [item.record.memory for item in memories]
    assert "Fact discussed: User lives in Bangalore." in memory_texts
    assert "Student goal: User wants AIR 1 in GATE CSE." in memory_texts
    assert "Learning preference: User prefers hands-on learning." in memory_texts
    assert "Knowledge state: User studied Binary Search Tree." not in memory_texts
    assert "The user asked about another user's previous request." not in memory_texts


def test_prompt_receives_only_filtered_relevant_memories(tmp_path: Path) -> None:
    class CapturingLlmClient:
        system_prompt = ""

        def generate_text(self, *args: object, **kwargs: object) -> str:
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompt = str(kwargs["system_prompt"])
            return "- Process Scheduling"

    repository = ChromaChatRepository(tmp_path / "chroma")
    user_id = "student-a@example.com"
    for index, (memory, memory_type, topic) in enumerate(
        [
            ("User is preparing for GATE.", "goal", "GATE"),
            ("Explained Binary Search Tree.", "knowledge_state", "BST"),
            ("Explained Operating System process scheduling.", "knowledge_state", "Operating System"),
            ("Explained Depth First Search.", "knowledge_state", "DFS"),
            ("User prefers concise answers.", "preference", None),
        ]
    ):
        repository.save_memory(
            MemoryRecord(
                id=f"memory-{index}",
                user_id=user_id,
                timestamp=utc_now(),
                memory=memory,
                importance=8,
                type=memory_type,
                topic=topic,
                status="active",
            )
        )

    llm_client = CapturingLlmClient()
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    user_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id=user_id,
        role="user",
        content="List the topics covered in Operating System.",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(user_message)

    orchestrator.generate_reply("chat-a", user_message)

    assert orchestrator._last_context is not None
    assert [
        item.content for item in orchestrator._last_context.memory_context
    ] == ["Explained Operating System process scheduling."]
    assert "Explained Operating System process scheduling." in llm_client.system_prompt
    assert "Explained Binary Search Tree." not in llm_client.system_prompt
    assert "Explained Depth First Search." not in llm_client.system_prompt
    assert "User is preparing for GATE." not in llm_client.system_prompt
    assert "User prefers concise answers." not in llm_client.system_prompt
    assert "Memory Retrieval Context contains the only retrieved memories" in llm_client.system_prompt
    assert "Do not invent previous conversations" in llm_client.system_prompt


def test_about_me_prompt_injects_only_profile_style_memory_context(tmp_path: Path) -> None:
    class CapturingLlmClient:
        system_prompt = ""

        def generate_text(self, *args: object, **kwargs: object) -> str:
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompt = str(kwargs["system_prompt"])
            return "Profile summary"

    repository = ChromaChatRepository(tmp_path / "chroma")
    user_id = "student-a@example.com"
    for index, (memory, memory_type, topic) in enumerate(
        [
            ("Fact discussed: User lives in Bangalore.", "fact", "Bangalore"),
            ("Student goal: User wants AIR 1 in GATE CSE.", "goal", "GATE"),
            ("Knowledge state: User studied Binary Search Tree.", "knowledge_state", "BST"),
            (
                "The user asked about another user's previous request.",
                "conversation_event",
                None,
            ),
        ]
    ):
        repository.save_memory(
            MemoryRecord(
                id=f"memory-{index}",
                user_id=user_id,
                timestamp=utc_now(),
                memory=memory,
                importance=8,
                type=memory_type,
                topic=topic,
                status="active",
            )
        )

    llm_client = CapturingLlmClient()
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    user_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id=user_id,
        role="user",
        content="What do you remember about me?",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(user_message)

    orchestrator.generate_reply("chat-a", user_message)

    assert "Fact discussed: User lives in Bangalore." in llm_client.system_prompt
    assert "Student goal: User wants AIR 1 in GATE CSE." in llm_client.system_prompt
    assert "Knowledge state: User studied Binary Search Tree." not in llm_client.system_prompt
    assert "The user asked about another user's previous request." not in llm_client.system_prompt


def test_project_memory_query_uses_retrieved_memory_context(tmp_path: Path) -> None:
    class CapturingLlmClient:
        system_prompt = ""

        def generate_text(self, *args: object, **kwargs: object) -> str:
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompt = str(kwargs["system_prompt"])
            return "- AI tutor using FastAPI"

    repository = ChromaChatRepository(tmp_path / "chroma")
    user_id = "student-a@example.com"
    repository.save_memory(
        MemoryRecord(
            id="memory-project",
            user_id=user_id,
            timestamp=utc_now(),
            memory="User is building an AI tutor using FastAPI.",
            importance=8,
            type="achievement",
            topic="AI tutor",
            status="active",
        )
    )

    llm_client = CapturingLlmClient()
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    user_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id=user_id,
        role="user",
        content="What projects have I worked on?",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(user_message)

    reply = orchestrator.generate_reply("chat-a", user_message)

    assert reply == "- AI tutor using FastAPI"
    assert orchestrator._last_context is not None
    assert [
        item.content for item in orchestrator._last_context.memory_context
    ] == ["User is building an AI tutor using FastAPI."]
    assert "memory_history_request: project_memory" in llm_client.system_prompt
    assert "User is building an AI tutor using FastAPI." in llm_client.system_prompt


def test_continue_after_coding_stays_in_coding_mode(tmp_path: Path) -> None:
    class CodingLlmClient:
        system_prompts: list[str] = []

        def generate_text(self, *args: object, **kwargs: object) -> str:
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompts.append(str(kwargs["system_prompt"]))
            return "code part"

    llm_client = CodingLlmClient()
    repository = ChromaChatRepository(tmp_path / "chroma")
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    first_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id="student-a@example.com",
        role="user",
        content="Write a Python class for a linked list",
        timestamp=utc_now(),
        session_id="session-a",
    )
    continue_message = Message(
        id="message-b",
        chat_id="chat-a",
        user_id="student-a@example.com",
        role="user",
        content="Continue",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(first_message)
    repository.save_message(continue_message)

    orchestrator.generate_reply("chat-a", first_message)
    orchestrator.generate_reply("chat-a", continue_message)

    assert "Response mode: coding" in llm_client.system_prompts[0]
    assert "Response mode: coding" in llm_client.system_prompts[1]


def test_first_conversation_question_uses_permanent_memory_not_raw_chat(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma", MemoryRenderingLlmClient()) as client:
        headers = {"X-User-Id": "student-a@example.com"}

        first_chat = client.post("/chat/create", json={}, headers=headers).json()
        client.post(
            f"/chat/{first_chat['id']}/message",
            json={"content": "hi man"},
            headers=headers,
        )
        client.post(
            f"/chat/{first_chat['id']}/message",
            json={"content": "I want to learn calculus"},
            headers=headers,
        )

        second_chat = client.post("/chat/create", json={}, headers=headers).json()
        response = client.post(
            f"/chat/{second_chat['id']}/message",
            json={"content": "what was the first time i converse wid u"},
            headers=headers,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert "first permanent learning memory" in assistant_reply
        assert "I want to learn calculus" in assistant_reply
        assert "hi man" not in assistant_reply
        assert "blank slate" not in assistant_reply
        assert "don't have personal memories" not in assistant_reply

        repository = ChromaChatRepository(tmp_path / "chroma")
        memories = repository.list_memories("student-a@example.com")
        assert len(memories) == 1
        stored_memory = json.loads(memories[0].memory)
        assert stored_memory["topic"] == "calculus"
        assert "Student goal: I want to learn calculus" in stored_memory["important_facts"]


def test_conversation_summary_question_uses_saved_chat_history(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma", MemoryRenderingLlmClient()) as client:
        headers = {"X-User-Id": "student-a@example.com"}

        first_chat = client.post("/chat/create", json={}, headers=headers).json()
        client.post(
            f"/chat/{first_chat['id']}/message",
            json={"content": "I want to learn FastAPI for my tutor chatbot"},
            headers=headers,
        )
        client.post(
            f"/chat/{first_chat['id']}/message",
            json={"content": "I learned ChromaDB stores the messages"},
            headers=headers,
        )

        second_chat = client.post("/chat/create", json={}, headers=headers).json()
        response = client.post(
            f"/chat/{second_chat['id']}/message",
            json={"content": "what did we discuss can u make a summary"},
            headers=headers,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert "what I remember from our earlier learning" in assistant_reply
        assert "Earlier learning topics" in assistant_reply
        assert "useful timeline" not in assistant_reply
        assert "Earlier questions/topics" not in assistant_reply
        assert "UTC" not in assistant_reply
        assert "I want to learn FastAPI for my tutor chatbot" in assistant_reply
        assert "I learned ChromaDB stores the messages" in assistant_reply
        assert "not much to summarize" not in assistant_reply
        assert "Our conversation just started" not in assistant_reply


def test_resume_previous_topic_does_not_dump_timeline(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma", MemoryRenderingLlmClient()) as client:
        headers = {"X-User-Id": "student-a@example.com"}

        first_chat = client.post("/chat/create", json={}, headers=headers).json()
        client.post(
            f"/chat/{first_chat['id']}/message",
            json={"content": "can u maybe make a table and explain"},
            headers=headers,
        )
        client.post(
            f"/chat/{first_chat['id']}/message",
            json={"content": "btw what is usa government password"},
            headers=headers,
        )

        second_chat = client.post("/chat/create", json={}, headers=headers).json()
        response = client.post(
            f"/chat/{second_chat['id']}/message",
            json={"content": "hey so can we continue what we discussed earlier?"},
            headers=headers,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert "let's continue from btw what is usa government password" in assistant_reply
        assert "quick recap" in assistant_reply
        assert "useful timeline" not in assistant_reply
        assert "Earlier questions/topics" not in assistant_reply
        assert "UTC" not in assistant_reply


def test_conversation_summary_ignores_small_talk_and_keeps_technical_topics(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma", MemoryRenderingLlmClient()) as client:
        headers = {"X-User-Id": "student-a@example.com"}

        first_chat = client.post("/chat/create", json={}, headers=headers).json()
        for content in [
            "ok what are u",
            "k",
            "wsp man",
            ".",
            "what is photosynthesis in biology",
            "explain DNA replication",
            "HI do u remember me",
        ]:
            client.post(
                f"/chat/{first_chat['id']}/message",
                json={"content": content},
                headers=headers,
            )

        second_chat = client.post("/chat/create", json={}, headers=headers).json()
        response = client.post(
            f"/chat/{second_chat['id']}/message",
            json={"content": "what did we discuss can u make a summary"},
            headers=headers,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert "what is photosynthesis in biology" in assistant_reply
        assert "explain DNA replication" in assistant_reply
        assert "ok what are u" not in assistant_reply
        assert "wsp man" not in assistant_reply
        assert "HI do u remember me" not in assistant_reply

        repository = ChromaChatRepository(tmp_path / "chroma")
        memories = [memory.memory for memory in repository.list_memories("student-a@example.com")]
        assert "Student is learning what did we discuss can u make a summary." not in memories
        assert any("photosynthesis" in memory.lower() for memory in memories)
        assert any("dna replication" in memory.lower() for memory in memories)


def test_list_discussed_topics_returns_only_topic_names(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma", MemoryRenderingLlmClient()) as client:
        headers = {"X-User-Id": "student-a@example.com"}
        chat = client.post("/chat/create", json={}, headers=headers).json()

        for content in [
            "Explain DFS",
            "What is Binary Search Tree?",
        ]:
            client.post(
                f"/chat/{chat['id']}/message",
                json={"content": content},
                headers=headers,
            )

        response = client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "List the topics we discussed."},
            headers=headers,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert assistant_reply == "- Depth First Search (DFS)\n- Binary Search Tree (BST)"
        assert "Definition" not in assistant_reply
        assert "Working" not in assistant_reply
        assert "Example" not in assistant_reply
        assert "Would you like" not in assistant_reply


def test_current_conversation_topic_question_does_not_use_chroma_memories(
    tmp_path: Path,
) -> None:
    class CapturingLlmClient(MemoryRenderingLlmClient):
        pass

    llm_client = CapturingLlmClient()
    repository = ChromaChatRepository(tmp_path / "chroma")
    user_id = "student-a@example.com"
    repository.save_memory(
        MemoryRecord(
            id="memory-gate",
            user_id=user_id,
            timestamp=utc_now(),
            memory="Student goal: GATE preparation",
            importance=10,
            type="goal",
            topic="GATE",
            status="active",
        )
    )

    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    first_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id=user_id,
        role="user",
        content="Explain linked lists",
        timestamp=utc_now(),
        session_id="session-a",
    )
    question = Message(
        id="message-b",
        chat_id="chat-a",
        user_id=user_id,
        role="user",
        content="What topics did we discuss?",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(first_message)
    repository.save_message(question)

    reply = orchestrator.generate_reply("chat-a", question)

    assert "Linked Lists" in reply or "linked lists" in reply
    assert "GATE" not in reply
    assert orchestrator._last_context is not None
    assert orchestrator._last_context.memory_context == []
    assert "Student goal: GATE preparation" not in llm_client.system_prompts[-1]


def test_user_profile_query_uses_chroma_profile_memories(tmp_path: Path) -> None:
    class CapturingLlmClient:
        system_prompt = ""

        def generate_text(self, *args: object, **kwargs: object) -> str:
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompt = str(kwargs["system_prompt"])
            return "Your goal is AIR 1 in GATE CSE."

    repository = ChromaChatRepository(tmp_path / "chroma")
    user_id = "student-a@example.com"
    repository.save_memory(
        MemoryRecord(
            id="memory-goal",
            user_id=user_id,
            timestamp=utc_now(),
            memory="Student goal: User wants AIR 1 in GATE CSE.",
            importance=10,
            type="goal",
            topic="GATE",
            status="active",
        )
    )

    llm_client = CapturingLlmClient()
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    user_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id=user_id,
        role="user",
        content="What are my goals?",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(user_message)

    orchestrator.generate_reply("chat-a", user_message)

    assert orchestrator._last_context is not None
    assert [
        item.content for item in orchestrator._last_context.memory_context
    ] == ["Student goal: User wants AIR 1 in GATE CSE."]
    assert "Student goal: User wants AIR 1 in GATE CSE." in llm_client.system_prompt


def test_knowledge_query_retrieves_only_knowledge_memories(tmp_path: Path) -> None:
    class CapturingLlmClient:
        system_prompt = ""

        def generate_text(self, *args: object, **kwargs: object) -> str:
            user_content = str(kwargs.get("user_content", ""))
            if "Return ONLY a JSON array of 4-6 teaching headings." in user_content:
                return '["Definition","Working","Example","Complexity"]'
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompt = str(kwargs["system_prompt"])
            return "Recursion explanation"

    repository = ChromaChatRepository(tmp_path / "chroma")
    user_id = "student-a@example.com"
    for memory_id, memory, memory_type, topic in [
        ("memory-goal", "Student goal: User wants AIR 1 in GATE CSE.", "goal", "GATE"),
        (
            "memory-recursion",
            "Knowledge state: User studied recursion basics.",
            "knowledge_state",
            "Recursion",
        ),
    ]:
        repository.save_memory(
            MemoryRecord(
                id=memory_id,
                user_id=user_id,
                timestamp=utc_now(),
                memory=memory,
                importance=8,
                type=memory_type,
                topic=topic,
                status="active",
            )
        )

    llm_client = CapturingLlmClient()
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    user_message = Message(
        id="message-a",
        chat_id="chat-a",
        user_id=user_id,
        role="user",
        content="Explain recursion",
        timestamp=utc_now(),
        session_id="session-a",
    )
    repository.save_message(user_message)

    orchestrator.generate_reply("chat-a", user_message)

    assert orchestrator._last_context is not None
    assert [
        item.content for item in orchestrator._last_context.memory_context
    ] == ["Knowledge state: User studied recursion basics."]
    assert "Knowledge state: User studied recursion basics." in llm_client.system_prompt
    assert "Student goal: User wants AIR 1 in GATE CSE." not in llm_client.system_prompt


def test_general_list_topic_request_uses_ai_not_discussed_topic_shortcut(
    tmp_path: Path,
) -> None:
    class ListLlmClient:
        system_prompt = ""

        def generate_text(self, *args: object, **kwargs: object) -> str:
            return '{"action":"NOOP","category":null,"memory":null,"target_memory_id":null,"reason":"test"}'

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.system_prompt = str(kwargs["system_prompt"])
            return "- Process Management\n- Memory Management\n- File Systems"

    llm_client = ListLlmClient()
    repository = ChromaChatRepository(tmp_path / "chroma")
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]
    for index, content in enumerate(
        [
            "Explain DFS",
            "What is Binary Search Tree?",
            "List the topics covered in Operating System.",
        ]
    ):
        repository.save_message(
            Message(
                id=f"message-{index}",
                chat_id="chat-a",
                user_id="student-a@example.com",
                role="user",
                content=content,
                timestamp=utc_now(),
                session_id="session-a",
            )
        )

    reply = orchestrator.generate_reply(
        "chat-a",
        Message(
            id="message-2",
            chat_id="chat-a",
            user_id="student-a@example.com",
            role="user",
            content="List the topics covered in Operating System.",
            timestamp=utc_now(),
            session_id="session-a",
        ),
    )

    assert reply == "- Process Management\n- Memory Management\n- File Systems"
    assert "Response mode: list" in llm_client.system_prompt
    assert "LIST mode: return only the requested list." in llm_client.system_prompt
    assert "Depth First Search (DFS)" not in reply
    assert "Binary Search Tree (BST)" not in reply


def test_short_factual_learning_prompt_is_not_treated_as_small_talk(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        headers = {"X-User-Id": "student-a@example.com"}
        chat = client.post("/chat/create", json={}, headers=headers).json()

        response = client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "china capital"},
            headers=headers,
        )

        assert response.status_code == 201
        repository = ChromaChatRepository(tmp_path / "chroma")
        memories = [memory.memory for memory in repository.list_memories("student-a@example.com")]
        stored_memory = json.loads(memories[0])
        assert stored_memory["topic"] == "china capital"
        assert "Fact discussed: china capital" in stored_memory["important_facts"]


def test_conversation_summary_is_filtered_by_user(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma", MemoryRenderingLlmClient()) as client:
        user_a = {"X-User-Id": "student-a@example.com"}
        user_b = {"X-User-Id": "student-b@example.com"}

        chat_a = client.post("/chat/create", json={}, headers=user_a).json()
        client.post(
            f"/chat/{chat_a['id']}/message",
            json={"content": "I want to learn LangGraph privately"},
            headers=user_a,
        )

        chat_b = client.post("/chat/create", json={}, headers=user_b).json()
        response = client.post(
            f"/chat/{chat_b['id']}/message",
            json={"content": "what did we discuss can u make a summary"},
            headers=user_b,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert "LangGraph privately" not in assistant_reply
        assert "do not remember an earlier learning discussion" in assistant_reply


def test_targeted_history_question_searches_saved_transcript(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma", MemoryRenderingLlmClient()) as client:
        headers = {"X-User-Id": "student-a@example.com"}

        first_chat = client.post("/chat/create", json={}, headers=headers).json()
        client.post(
            f"/chat/{first_chat['id']}/message",
            json={"content": "write a short story between two people at a railway station"},
            headers=headers,
        )

        second_chat = client.post("/chat/create", json={}, headers=headers).json()
        response = client.post(
            f"/chat/{second_chat['id']}/message",
            json={"content": "oh did we discuss any story between 2 ppl?"},
            headers=headers,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert "I remember something related" in assistant_reply
        assert "UTC" not in assistant_reply
        assert "story between two people" in assistant_reply
        assert "could not find" not in assistant_reply
        assert "haven't discussed" not in assistant_reply


def test_targeted_history_question_does_not_leak_other_users_transcript(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma", MemoryRenderingLlmClient()) as client:
        user_a = {"X-User-Id": "student-a@example.com"}
        user_b = {"X-User-Id": "student-b@example.com"}

        chat_a = client.post("/chat/create", json={}, headers=user_a).json()
        client.post(
            f"/chat/{chat_a['id']}/message",
            json={"content": "write a short story between two people at a railway station"},
            headers=user_a,
        )

        chat_b = client.post("/chat/create", json={}, headers=user_b).json()
        response = client.post(
            f"/chat/{chat_b['id']}/message",
            json={"content": "oh did we discuss any story between 2 ppl?"},
            headers=user_b,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert "railway station" not in assistant_reply
        assert "do not remember us discussing" in assistant_reply


def test_working_memory_filters_prior_small_talk_but_keeps_current_turn(tmp_path: Path) -> None:
    repository = ChromaChatRepository(tmp_path / "chroma")
    orchestrator = TutorOrchestrator(repository)
    contents = [
        "hi",
        "k",
        "what is photosynthesis in biology",
        "HI do u remember me",
        "explain DNA replication",
    ]
    messages = [
        Message(
            id=f"message-{index}",
            chat_id="chat-a",
            user_id="student-a@example.com",
            role="user",
            content=content,
            timestamp=utc_now(),
            session_id="session-a",
        )
        for index, content in enumerate(contents)
    ]
    for message in messages:
        repository.save_message(message)

    orchestrator.generate_reply("chat-a", messages[-1])

    assert orchestrator._last_context is not None
    working_contents = [
        message.content for message in orchestrator._last_context.memory.working_messages
    ]
    assert "what is photosynthesis in biology" in working_contents
    assert "explain DNA replication" in working_contents
    assert "hi" not in working_contents
    assert "k" not in working_contents
    assert "HI do u remember me" not in working_contents


def test_i_see_is_treated_as_understanding_not_confusion(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        headers = {"X-User-Id": "student-a@example.com"}
        chat = client.post("/chat/create", json={}, headers=headers).json()
        client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "oh did we discuss any story between 2 ppl?"},
            headers=headers,
        )

        response = client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "i see"},
            headers=headers,
        )

        assert response.status_code == 201
        assistant_reply = response.json()["assistant_message"]["content"]
        assert assistant_reply == "Nice. That means we can build on this now."
        assert "not sure what you're referring to" not in assistant_reply
        assert "elaborate" not in assistant_reply


def test_memory_lookup_question_is_not_promoted_to_permanent_memory(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        headers = {"X-User-Id": "student-a@example.com"}
        chat = client.post("/chat/create", json={}, headers=headers).json()

        response = client.post(
            f"/chat/{chat['id']}/message",
            json={"content": "what was the first time i converse wid u"},
            headers=headers,
        )

        assert response.status_code == 201
        repository = ChromaChatRepository(tmp_path / "chroma")
        assert repository.list_memories("student-a@example.com") == []


def test_gratitude_bypasses_llm_even_when_client_exists(tmp_path: Path) -> None:
    class FakeLlmClient:
        called = False

        def generate_reply(self, *args: object, **kwargs: object) -> str:
            self.called = True
            return "This should not be used."

    llm_client = FakeLlmClient()
    repository = ChromaChatRepository(tmp_path / "chroma")
    orchestrator = TutorOrchestrator(repository, llm_client)  # type: ignore[arg-type]

    reply = orchestrator.generate_reply(
        "chat-a",
        Message(
            id="message-a",
            chat_id="chat-a",
            user_id="student-a@example.com",
            role="user",
            content="ty so much",
            timestamp=utc_now(),
            session_id="session-a",
        ),
    )

    assert reply == "Happy to help. Glad it clicked."
    assert llm_client.called is False


def test_health_endpoint(tmp_path: Path) -> None:
    with build_client(tmp_path / "chroma") as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
