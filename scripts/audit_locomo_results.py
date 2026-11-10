"""Audit official-data results and exercise the real FastAPI chat route locally."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

from run_official_locomo import (
    conversation_messages, digest, load_official_scorer, summarize,
)


def cosine(left, right):
    return sum(a*b for a, b in zip(left, right)) / (
        math.sqrt(sum(a*a for a in left)) * math.sqrt(sum(b*b for b in right)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--scorer", type=Path, required=True)
    parser.add_argument("--app-root", type=Path,
                        default=Path("/Users/amitoj/Developer/AITutor"))
    args = parser.parse_args()
    sys.path.insert(0, str(args.app_root))
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    import chromadb
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.chat import router
    from backend.database.chroma_repository import ChromaChatRepository
    from backend.llm.groq_client import GroqClient
    from backend.memory.semantic_chat import SemanticChatMemory
    from backend.models.chat import Message, ChatSummary
    from backend.services.chat_service import ChatService

    manifest = json.loads((args.run / "manifest.json").read_text())
    rows = [json.loads(line) for line in (args.run / "predictions.jsonl").read_text().splitlines()]
    samples = {s["sample_id"]: s for s in json.loads(args.dataset.read_text())}
    scorer = load_official_scorer(args.scorer)
    report = {"dataset_hash_matches": digest(args.dataset) == manifest["dataset_sha256"],
              "upstream_scorer_hash_matches": digest(args.scorer) == manifest["scorer_sha256"],
              "prediction_count": len(rows), "errors": [], "score_mismatches": [],
              "reference_mismatches": [], "cosine_checks": [], "api_checks": []}
    if not report["dataset_hash_matches"] or not report["upstream_scorer_hash_matches"]:
        raise ValueError("Official files differ from the experiment's recorded hashes")
    for row in rows:
        qa = samples[row["sample_id"]]["qa"][row["qa_index"]]
        if row.get("question") != qa["question"] or row.get("reference_answer") != qa.get("answer"):
            report["reference_mismatches"].append([row["sample_id"], row["qa_index"]])
        if "error" in row:
            report["errors"].append(row["error"])
            continue
        value = float(scorer["eval_question_answering"](
            [dict(qa, answer=qa.get("answer", ""), prediction=row["prediction"])])[0][0])
        if abs(value - row["official_score"]) > 1e-10:
            report["score_mismatches"].append([row["sample_id"], row["qa_index"], value])
    expected = sum(len(v) for v in manifest["selected_questions"].values()) * 2
    report["expected_prediction_count"] = expected
    report["unique_prediction_count"] = len({(r["sample_id"], r["qa_index"], r["mode"]) for r in rows})
    report["all_input_bounds_valid"] = all(
        r["prompt_token_upper_bound"] <= r["configured_input_budget"]
        for r in rows if "error" not in r)
    report["all_predictions_finished_without_token_truncation"] = all(
        r.get("finish_reason") == "stop" for r in rows)
    report["recomputed_summary_matches"] = summarize(rows) == json.loads(
        (args.run / "summary.json").read_text())["results"]

    client = chromadb.PersistentClient(path=str(args.run / "test_chroma"))
    checked = 0
    # Recompute cosine using full saved vectors, not just trust logged numbers.
    for row in [r for r in rows if r["mode"] == "hybrid"][:5]:
        trace = row["memory_trace"]
        collection = client.get_collection(trace["collection"], embedding_function=None)
        memory = SemanticChatMemory(type("Repo", (), {"_client": client})(),
            "http://127.0.0.1:1234/v1", trace["embedding_model"])
        query_vector = memory.embed([row["question"]], query=True)[0]
        for item in trace["retrieved_memories"]:
            record = collection.get(ids=[item["id"]], include=["embeddings"])
            computed = float(cosine(query_vector, record["embeddings"][0]))
            report["cosine_checks"].append({"message_id": item["id"],
                "logged": item["cosine_similarity"], "recomputed": computed,
                "matches": abs(computed-item["cosine_similarity"]) < 1e-4})
            checked += 1
    report["cosine_records_checked"] = checked

    # New isolated storage per case: use real route, repository, service and client.
    # Deliberately inspect a temporal failure as well as a successful recall case.
    sample = next(iter(samples.values()))
    for qa_index in (0, 82):
        qa = sample["qa"][qa_index]
        root = args.run / ("api_audit_" + str(qa_index))
        if root.exists():
            raise ValueError("API audit storage already exists; do not reuse contaminated memory")
        repo = ChromaChatRepository(root)
        history = conversation_messages(sample, Message)
        now = datetime.now(timezone.utc)
        repo.save_chat(ChatSummary(id=sample["sample_id"], title="Isolated official-data API test",
            user_id=history[0].user_id, session_id="evaluation", created_at=now, updated_at=now))
        repo._write_json_file(repo._message_file, {m.id: m.model_dump_json() for m in history})
        memory = SemanticChatMemory(repo, "http://127.0.0.1:1234/v1",
                                   "text-embedding-nomic-embed-text-v1.5")
        repo.semantic_memory = memory
        memory.sync(history[0].user_id)
        model = GroqClient(api_key="local", model="qwen2.5-1.5b-instruct",
            base_url="http://127.0.0.1:1234/v1", temperature=.1, num_predict=128,
            timeout_seconds=180)
        service = ChatService(repo, model, semantic_memory=memory,
                              prompt_token_budget=2800, memory_min_similarity=.6)
        app = FastAPI()
        app.include_router(router)
        app.state.chat_service = service
        before = time.perf_counter()
        with TestClient(app) as api:
            response = api.post(f'/chat/{sample["sample_id"]}/message',
                headers={"X-User-Id": history[0].user_id}, json={"content": qa["question"]})
            response.raise_for_status()
            result = response.json()
        prediction = result["assistant_message"]["content"]
        score = float(scorer["eval_question_answering"](
            [dict(qa, answer=qa.get("answer", ""), prediction=prediction)])[0][0])
        stored = repo.get_chat(sample["sample_id"], history[0].user_id)
        saved_messages = repo.list_messages(sample["sample_id"], history[0].user_id)
        ids = {m.id for m in saved_messages}
        indexed = memory.collection.get(ids=[result["assistant_message"]["id"]])["ids"]
        report["api_checks"].append({"qa_index": qa_index, "question": qa["question"],
            "reference": qa.get("answer"), "prediction": prediction, "official_score": score,
            "http_status": response.status_code,
            "user_message_saved": result["user_message"]["id"] in ids,
            "assistant_message_saved": result["assistant_message"]["id"] in ids,
            "assistant_embedding_saved": bool(indexed),
            "latency_ms": (time.perf_counter()-before)*1000,
            "memory_trace": result["assistant_message"].get("memory_trace")})
    report["score_audit_passed"] = not report["score_mismatches"] and not report["reference_mismatches"]
    report["cosine_audit_passed"] = all(item["matches"] for item in report["cosine_checks"])
    (args.run / "audit.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in {"api_checks", "cosine_checks"}}, indent=2))
    print(json.dumps([{k:v for k,v in r.items() if k != "memory_trace"}
                      for r in report["api_checks"]], indent=2))


if __name__ == "__main__":
    main()
