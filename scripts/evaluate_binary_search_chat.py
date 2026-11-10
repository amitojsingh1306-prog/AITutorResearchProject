"""Custom screenshot-based retention test, not the official LoCoMo benchmark.

Seed only the two user statements from the screenshots. Each question runs in
its own process and temporary database so predictions cannot seed later tests.
Uses the actual FastAPI chat route, Nomic, Chroma and local Qwen.
"""

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from uuid import uuid4


HISTORY = [
    "My name is Amitoj. I'm learning binary search in Python. "
    "I prefer short explanations using numbered steps.",
    "I keep confusing low, high, and mid. Remember that this is my main difficulty.",
]
CASES = [
    ("Which programming algorithm was I learning?", "binary search"),
    ("What is my main difficulty with that algorithm?", "low high mid"),
    ("How do I prefer explanations?", "short explanations using numbered steps"),
    (
        "What did I tell you about my name, what I am learning, "
        "and how I prefer explanations?",
        HISTORY[0],
    ),
]


def tokens(text):
    """Declared simple overlap metric, without claiming the official scorer."""
    return re.sub(r"\b(a|an|the)\b", " ",
                  re.sub(r"[^\w\s]", " ", text.lower())).split()


def overlap_metrics(prediction, reference):
    predicted, expected = tokens(prediction), tokens(reference)
    common = sum((Counter(predicted) & Counter(expected)).values())
    precision = common / len(predicted) if predicted else 0.0
    recall = common / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return dict(matching_tokens=common, predicted_tokens=len(predicted),
                reference_tokens=len(expected), precision=precision, recall=recall,
                f1=f1, normalized_exact_match=predicted == expected)


def worker(args):
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    sys.path.insert(0, str(args.app_root))
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.chat import router
    from backend.database.chroma_repository import ChromaChatRepository
    from backend.llm.groq_client import GroqClient
    from backend.memory.semantic_chat import SemanticChatMemory
    from backend.models.chat import ChatSummary, Message
    from backend.services.chat_service import ChatService

    user, chat = "isolated-binary-search-test", str(uuid4())
    now = datetime.now(timezone.utc)
    repo = ChromaChatRepository(args.storage)
    repo.save_chat(ChatSummary(id=chat, title="Screenshot retention test",
        user_id=user, session_id=chat, created_at=now, updated_at=now))
    for i, content in enumerate(HISTORY):
        repo.save_message(Message(id=str(uuid4()), chat_id=chat, user_id=user,
            session_id=chat, role="user", content=content,
            timestamp=now + timedelta(seconds=i)))
    memory = SemanticChatMemory(repo, args.model_url,
                               "text-embedding-nomic-embed-text-v1.5")
    repo.semantic_memory = memory
    memory.sync(user)
    # This legacy class name still uses the explicitly local URL below.
    llm = GroqClient(api_key="local", model=args.model, base_url=args.model_url,
                    temperature=0.1, num_predict=128, timeout_seconds=180)
    app = FastAPI()
    app.include_router(router)
    app.state.chat_service = ChatService(repo, llm, semantic_memory=memory,
        prompt_token_budget=2800, memory_min_similarity=0.6)
    question, reference = CASES[args.case]
    start = time.perf_counter()
    with TestClient(app) as client:
        response = client.post(f"/chat/{chat}/message",
            headers={"X-User-Id": user}, json={"content": question})
        response.raise_for_status()
    elapsed = (time.perf_counter() - start) * 1000
    assistant = response.json()["assistant_message"]
    result = dict(question=question, reference=reference,
        answer=assistant["content"], metrics=overlap_metrics(assistant["content"], reference),
        request_latency_ms=elapsed, memory_trace=assistant.get("memory_trace"),
        scope="Custom short-history retention test; not official LoCoMo",
        model=args.model, history=HISTORY)
    args.result.write_text(json.dumps(result, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--model-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="qwen2.5-1.5b-instruct")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--storage", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--case", type=int)
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    if not args.model_url.startswith("http://127.0.0.1:"):
        parser.error("This test requires a local loopback model URL.")
    out = Path(tempfile.mkdtemp(prefix="binary-search-retention-report-"))
    print("Reports:", out, flush=True)
    for index in range(len(CASES)):
        result_file = out / f"case-{index}.json"
        with tempfile.TemporaryDirectory(prefix="binary-search-test-db-") as storage:
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker",
                "--app-root", str(args.app_root), "--model-url", args.model_url,
                "--model", args.model, "--case", str(index), "--storage", storage,
                "--result", str(result_file)], check=True)
        result = json.loads(result_file.read_text())
        print("\nQUESTION:", result["question"])
        print("REFERENCE:", result["reference"])
        print("QWEN ANSWER:", result["answer"])
        print("OVERLAP METRICS:", json.dumps(result["metrics"], indent=2))
        print("REQUEST LATENCY (ms):", round(result["request_latency_ms"], 2))
        trace = result["memory_trace"] or {}
        # Preserve the backend's role-aware ranking instead of inventing confidence.
        for candidate in trace.get("retrieved_memories", []):
            print("RETRIEVED:", json.dumps(candidate, default=str))
        print("HISTORY IN PROMPT:", trace.get("history_message_ids", []))
    print("\nCompleted:", out)


if __name__ == "__main__":
    main()
