"""End-to-end API tests using an isolated persistent ChromaDB."""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.agents.conversation_state_agent import ConversationStateAgent
from backend.agents.dialogue_manager_agent import DialogueManagerAgent
from backend.agents.intent_agent import IntentAgent
from backend.config import Settings
from backend.database.chroma_repository import ChromaChatRepository
from backend.main import create_app
from backend.models.chat import Message
from backend.models.learner import TeachingPlan
from backend.orchestration.tutor_orchestrator import TutorOrchestrator
from backend.utils.time import utc_now


def build_client(database_path: Path) -> TestClient:
    settings = Settings(chroma_path=database_path, api_key=None)
    return TestClient(create_app(settings))


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
    with build_client(tmp_path / "chroma") as client:
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
