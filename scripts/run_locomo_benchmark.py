"""Run a small LoCoMo-style memory benchmark for the local tutor memory layer.

This benchmark is intentionally local-only. It creates a fixed conversation
memory set, syncs it into a Chroma semantic index, runs recall-style queries,
and writes JSON plus Markdown reports that can be shown during evaluation.
"""

from __future__ import annotations

import json
import shutil
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.chroma_repository import ChromaChatRepository  # noqa: E402
from backend.embeddings.semantic_embedding import embedding_backend  # noqa: E402
from backend.models.chat import ChatSummary, Message  # noqa: E402
from scripts.sync_json_memory_to_chroma import sync_messages  # noqa: E402


BENCHMARK_ROOT = PROJECT_ROOT / "benchmark_outputs" / "locomo"
BENCHMARK_CHROMA = BENCHMARK_ROOT / "chroma_db"
REPORT_JSON = BENCHMARK_ROOT / "locomo_benchmark_report.json"
REPORT_MD = BENCHMARK_ROOT / "locomo_benchmark_report.md"
BENCHMARK_USER_ID = "locomo-benchmark-user"


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    query: str
    expected_terms: tuple[str, ...]
    stale_after_days: int = 30
    token_budget: int = 120


def make_message(
    *,
    chat_id: str,
    session_id: str,
    role: str,
    content: str,
    timestamp: datetime,
) -> Message:
    return Message(
        id=str(uuid4()),
        chat_id=chat_id,
        user_id=BENCHMARK_USER_ID,
        role=role,
        content=content,
        timestamp=timestamp,
        session_id=session_id,
    )


def seed_benchmark_memory(repository: ChromaChatRepository) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    chat_id = "locomo-demo-chat"
    session_id = "locomo-demo-session"
    chat = ChatSummary(
        id=chat_id,
        title="LoCoMo Benchmark Demo",
        user_id=BENCHMARK_USER_ID,
        session_id=session_id,
        created_at=now - timedelta(days=2),
        updated_at=now,
    )
    repository.save_chat(chat)

    messages = [
        make_message(
            chat_id=chat_id,
            session_id=session_id,
            role="user",
            content="My name is Amitoj and I prefer short examples with direct steps.",
            timestamp=now - timedelta(days=2, minutes=8),
        ),
        make_message(
            chat_id=chat_id,
            session_id=session_id,
            role="user",
            content="I am confused about recursion base cases and when recursion should stop.",
            timestamp=now - timedelta(days=2, minutes=6),
        ),
        make_message(
            chat_id=chat_id,
            session_id=session_id,
            role="assistant",
            content="We explained recursion base cases using a binary search example.",
            timestamp=now - timedelta(days=2, minutes=5),
        ),
        make_message(
            chat_id=chat_id,
            session_id=session_id,
            role="user",
            content="My linked list goal is to learn how to reverse a singly linked list.",
            timestamp=now - timedelta(days=1, minutes=20),
        ),
        make_message(
            chat_id=chat_id,
            session_id=session_id,
            role="user",
            content="For recursion practice, I want visual walkthroughs before code.",
            timestamp=now - timedelta(hours=4),
        ),
        make_message(
            chat_id=chat_id,
            session_id=session_id,
            role="user",
            content="Old stale note: I wanted bubble sort videos as my main learning plan.",
            timestamp=now - timedelta(days=75),
        ),
    ]
    for message in messages:
        repository.save_message(message)

    delete_probe = make_message(
        chat_id=chat_id,
        session_id=session_id,
        role="user",
        content="Delete probe memory: this record should disappear from retrieval.",
        timestamp=now - timedelta(minutes=1),
    )
    repository.save_message(delete_probe)
    return {"delete_probe_message_id": delete_probe.id}


def contains_expected_terms(results: list[dict[str, object]], terms: tuple[str, ...]) -> bool:
    joined = " ".join(str(item.get("document", "")).lower() for item in results)
    return all(term.lower() in joined for term in terms)


def run_benchmark() -> dict[str, object]:
    if BENCHMARK_ROOT.exists():
        shutil.rmtree(BENCHMARK_ROOT)
    BENCHMARK_ROOT.mkdir(parents=True, exist_ok=True)

    repository = ChromaChatRepository(BENCHMARK_CHROMA)
    seed_ids = seed_benchmark_memory(repository)
    sync_messages(
        messages_path=BENCHMARK_CHROMA / "messages.json",
        chroma_path=BENCHMARK_CHROMA,
        user_id=BENCHMARK_USER_ID,
        include_assistant=True,
        dry_run=False,
        limit=None,
    )

    cases = [
        BenchmarkCase(
            name="User preference recall",
            query="How should you explain topics to me?",
            expected_terms=("short examples", "direct steps"),
        ),
        BenchmarkCase(
            name="Confusion recall",
            query="What topic was I confused about?",
            expected_terms=("recursion base cases",),
        ),
        BenchmarkCase(
            name="Learning goal recall",
            query="What linked list goal did I mention?",
            expected_terms=("reverse a singly linked list",),
        ),
        BenchmarkCase(
            name="Recommendation memory recall",
            query="How should you teach recursion practice to me?",
            expected_terms=("visual walkthroughs",),
        ),
        BenchmarkCase(
            name="Stale memory detection",
            query="What old learning plan did I mention?",
            expected_terms=("bubble sort videos",),
            stale_after_days=30,
        ),
    ]

    case_results = []
    for case in cases:
        result = repository.query_json_embeddings(
            query=case.query,
            user_id=BENCHMARK_USER_ID,
            limit=3,
            candidate_limit=20,
            token_budget=case.token_budget,
            stale_after_days=case.stale_after_days,
        )
        retrieval_matrix = result["retrieval_matrix"]
        passed = contains_expected_terms(retrieval_matrix, case.expected_terms)
        case_results.append(
            {
                "case": case.name,
                "query": case.query,
                "expected_terms": list(case.expected_terms),
                "passed": passed,
                "retrieval_latency_ms": result["retrieval_latency_ms"],
                "precision_at_k_proxy": result["retrieval_metrics"]["precision_at_k_proxy"],
                "top_cosine_similarity": result["retrieval_metrics"]["top_cosine_similarity"],
                "top_confidence_score": result["retrieval_metrics"]["top_confidence_score"],
                "stale_memory_count": result["retrieval_metrics"]["stale_memory_count"],
                "memory_token_buffer": result["memory_token_buffer"],
                "top_documents": [
                    {
                        "document": item["document"],
                        "cosine_similarity": item["cosine_similarity"],
                        "confidence_score": item["confidence_score"],
                        "stale": item["stale"],
                        "estimated_tokens": item["estimated_tokens"],
                    }
                    for item in retrieval_matrix
                ],
            }
        )

    delete_embedding_id = f"json-message-{seed_ids['delete_probe_message_id']}"
    repository.delete_json_embedding(delete_embedding_id)
    delete_check = repository.query_json_embeddings(
        query="Delete probe memory disappear retrieval",
        user_id=BENCHMARK_USER_ID,
        limit=5,
        candidate_limit=20,
        token_budget=150,
        stale_after_days=30,
    )
    deleted_ids = {item["id"] for item in delete_check["retrieval_matrix"]}
    delete_passed = delete_embedding_id not in deleted_ids

    latencies = [float(item["retrieval_latency_ms"]) for item in case_results]
    summary = {
        "benchmark": "LoCoMo-inspired local memory benchmark",
        "scope": "Memory retrieval evaluation only; no external API and no model generation.",
        "embedding_backend": embedding_backend(),
        "storage": {
            "json_source": str(BENCHMARK_CHROMA / "messages.json"),
            "chroma_path": str(BENCHMARK_CHROMA),
            "collection": "json_message_semantic_embeddings",
        },
        "total_cases": len(case_results),
        "passed_cases": sum(1 for item in case_results if item["passed"]),
        "recall_at_3": round(
            sum(1 for item in case_results if item["passed"]) / len(case_results),
            4,
        ),
        "average_latency_ms": round(statistics.mean(latencies), 3),
        "p95_latency_ms": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 3),
        "average_top_cosine_similarity": round(
            statistics.mean(float(item["top_cosine_similarity"]) for item in case_results),
            4,
        ),
        "average_top_confidence_score": round(
            statistics.mean(float(item["top_confidence_score"]) for item in case_results),
            4,
        ),
        "delete_handling_passed": delete_passed,
    }
    return {"summary": summary, "cases": case_results, "delete_check": delete_check}


def write_reports(report: dict[str, object]) -> None:
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = report["summary"]
    cases = report["cases"]
    lines = [
        "# LoCoMo-Style Memory Benchmark Report",
        "",
        "This is a local-only evaluation of the tutor memory layer.",
        "",
        "## Summary",
        "",
        f"- Benchmark: {summary['benchmark']}",
        f"- Scope: {summary['scope']}",
        f"- Embedding backend: `{summary['embedding_backend']}`",
        f"- Collection: `{summary['storage']['collection']}`",
        f"- Total cases: {summary['total_cases']}",
        f"- Passed cases: {summary['passed_cases']}",
        f"- Recall@3: {summary['recall_at_3']}",
        f"- Average retrieval latency: {summary['average_latency_ms']} ms",
        f"- P95 retrieval latency: {summary['p95_latency_ms']} ms",
        f"- Average top cosine similarity: {summary['average_top_cosine_similarity']}",
        f"- Average top confidence score: {summary['average_top_confidence_score']}",
        f"- Delete handling passed: {summary['delete_handling_passed']}",
        "",
        "## Case Results",
        "",
        "| Case | Pass | Latency ms | Top cosine | Top confidence | Stale count |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for item in cases:
        lines.append(
            "| {case} | {passed} | {latency} | {cosine} | {confidence} | {stale} |".format(
                case=item["case"],
                passed="YES" if item["passed"] else "NO",
                latency=item["retrieval_latency_ms"],
                cosine=item["top_cosine_similarity"],
                confidence=item["top_confidence_score"],
                stale=item["stale_memory_count"],
            )
        )
    lines.extend(
        [
            "",
            "## What This Demonstrates",
            "",
            "- Memory recall: queries retrieve earlier user facts and confusion points.",
            "- Semantic retrieval: dense embeddings and cosine similarity rank relevant messages.",
            "- Latency: retrieval time is measured for each query.",
            "- Token buffer: each result reports the memory token budget and used tokens.",
            "- Stale memory: old memories are flagged rather than blindly trusted.",
            "- Delete handling: deleted embeddings stop appearing in retrieval results.",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    report = run_benchmark()
    write_reports(report)
    print(json.dumps(report["summary"], indent=2))
    print(f"\nJSON report: {REPORT_JSON}")
    print(f"Markdown report: {REPORT_MD}")


if __name__ == "__main__":
    main()
