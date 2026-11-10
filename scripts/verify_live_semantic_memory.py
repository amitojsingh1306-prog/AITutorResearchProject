"""Exercise actual API routes, local embeddings, Chroma and local Qwen.

Uses an isolated temporary database; never alters the user's chat history.
"""

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from backend.main import create_app
from backend.config import Settings
from backend.models.chat import Message


def main():
    with tempfile.TemporaryDirectory(prefix="aitutor-semantic-proof-") as directory:
        app = create_app(Settings(chroma_path=Path(directory), graph_enabled=False, mysql_enabled=False, memory_configuration='vector'))
        with TestClient(app) as client:
            headers = {"X-User-Id": "semantic-proof-user"}
            original = client.post("/chat/create", headers=headers, json={}).json()
            repository = app.state.chat_service._repository
            fact = Message(
                id=str(uuid4()), chat_id=original["id"], user_id=headers["X-User-Id"],
                session_id=original["session_id"], role="user",
                content="I need help understanding base cases in recursive functions. I prefer tracing factorial(5) on paper.",
                timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
            )
            repository.save_message(fact)
            for index in range(12):
                repository.save_message(fact.model_copy(update={
                    "id": str(uuid4()), "content": f"Unrelated physics exercise {index}: " + "Discuss momentum and force. " * 14,
                    "timestamp": fact.timestamp + timedelta(minutes=index + 1),
                }))
            foreign = fact.model_copy(update={"id": str(uuid4()), "user_id": "another-user",
                "content": "My secret recursion project is codeword PINEAPPLE."})
            repository.save_message(foreign)
            results = []
            for streaming in (False, True):
                chat = (client.post("/chat/create", headers=headers, json={}).json()
                        if streaming else original)
                response = client.post(
                    f'/chat/{chat["id"]}/message' + ("/stream" if streaming else ""),
                    headers=headers,
                    json={"content": "Which part of recursion did I need help with and what example did I prefer?"},
                )
                assert response.status_code in (200, 201), response.text
                if streaming:
                    events = []
                    for block in response.text.split("\n\n"):
                        lines = block.splitlines()
                        if len(lines) >= 2:
                            events.append((lines[0], json.loads(lines[1].removeprefix("data: "))))
                    assert not any(name == "event: error" for name, _ in events), events
                    assistant = next(data["assistant_message"] for name, data in events if name == "event: done")
                else:
                    assistant = response.json()["assistant_message"]
                trace = assistant["memory_trace"]
                hits = trace["retrieved_memories"]
                assert any(item["id"] == fact.id and item["included_in_prompt"] for item in hits), trace
                assert all(item["user_id"] == headers["X-User-Id"] for item in hits), trace
                assert fact.id not in trace["history_message_ids"], trace
                assert trace["prompt_token_upper_bound"] <= trace["prompt_token_budget"], trace
                text = assistant["content"].lower()
                assert "base case" in text and "factorial" in text, assistant
                assert "pineapple" not in text, assistant
                saved = repository.list_messages(chat["id"], headers["X-User-Id"])[-1]
                assert saved.memory_trace == trace
                results.append({"mode": "cross_chat_stream" if streaming else "beyond_eight_messages",
                                "answer": assistant["content"], "trace": trace})
                print(results[-1]["mode"], "PASS", flush=True)
            # Check dense vectors, source updates and index deletion reconciliation.
            record = repository.semantic_memory.collection.get(ids=[fact.id], include=["embeddings"])
            vector = record["embeddings"][0]
            assert len(vector) == 768 and sum(abs(float(v)) > 1e-8 for v in vector) > 700
            repository.save_message(fact.model_copy(update={"content": "I now understand base cases and am studying tree traversal."}))
            updated = repository.semantic_memory.collection.get(ids=[fact.id], include=["documents"])
            assert "tree traversal" in updated["documents"][0]
            messages = repository._read_json_file(repository._message_file)
            del messages[fact.id]
            repository._write_json_file(repository._message_file, messages)
            repository.semantic_memory.sync(headers["X-User-Id"])
            assert not repository.semantic_memory.collection.get(ids=[fact.id])["ids"]
            report = {"scope": "Live API integration verification, not official LoCoMo",
                      "dense_vectors": "PASS", "user_isolation": "PASS", "update_and_delete_sync": "PASS",
                      "results": results}
            output = Path(__file__).resolve().parents[1] / "benchmark_outputs" / "live_semantic_verification.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2))
            print("Proof report:", output, flush=True)


if __name__ == "__main__":
    main()
