"""Evaluate the local tutor on official LoCoMo data, not synthetic examples.

Uses the installed tutor's context builder and SemanticChatMemory. Model calls
are loopback-only. The supplied dataset and upstream scoring source are hashed.
No reference answers, QA questions, or predictions are indexed into memory.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
import time
from types import SimpleNamespace
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "benchmark_data" / "locomo"
SOURCE_URL = "https://github.com/snap-research/locomo"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_official_scorer(path):
    # Execute only the upstream pure QA scoring functions, not BERTScore imports.
    import numpy as np
    import regex
    import string
    from nltk.stem import PorterStemmer

    wanted = {"normalize_answer", "exact_match_score", "f1_score", "f1",
              "eval_question_answering"}
    tree = ast.parse(Path(path).read_text())
    functions = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name in wanted]
    if {f.name for f in functions} != wanted:
        raise ValueError("Upstream scoring functions changed; review before running")
    namespace = {"np": np, "regex": regex, "string": string,
                 "Counter": Counter, "ps": PorterStemmer()}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"),
         namespace)
    return namespace


def select_questions(qa, per_category=0):
    counts = Counter()
    chosen = []
    for index, item in enumerate(qa):
        category = int(item["category"])
        if per_category and counts[category] >= per_category:
            continue
        counts[category] += 1
        chosen.append((index, item))
    return chosen


def conversation_messages(sample, Message):
    conversation = sample["conversation"]
    messages = []
    sessions = sorted((key for key, value in conversation.items()
                       if re.fullmatch(r"session_\d+", key) and isinstance(value, list)),
                      key=lambda key: int(key.split("_")[1]))
    for session in sessions:
        date_text = conversation.get(session + "_date_time", "")
        date = datetime.strptime(date_text, "%I:%M %p on %d %B, %Y").replace(
            tzinfo=timezone.utc)
        for offset, turn in enumerate(conversation[session]):
            text = f'[{date_text}] {turn["speaker"]}: {turn["text"]}'
            if turn.get("blip_caption"):
                text += " [Provided image caption: " + str(turn["blip_caption"]) + "]"
            messages.append(Message(
                id=sample["sample_id"] + "::" + turn["dia_id"],
                chat_id=sample["sample_id"], user_id="benchmark-" + sample["sample_id"],
                session_id=session, role="user", content=text,
                timestamp=date + timedelta(seconds=offset),
            ))
    return messages


class TestRepository:
    """Isolated source history; both speakers are historical human statements."""
    def __init__(self, client, messages):
        self._client = client
        self.messages = messages

    def list_user_messages(self, user_id):
        return [m for m in self.messages if m.user_id == user_id]

    def list_messages(self, chat_id, user_id):
        return [m for m in self.messages if m.chat_id == chat_id and m.user_id == user_id]


def evidence_metrics(ids, expected):
    actual, gold = set(ids), set(expected)
    if not gold:
        return {"precision": None, "recall": None}
    common = len(actual & gold)
    return {"precision": common / len(actual) if actual else 0.0,
            "recall": common / len(gold)}


def summarize(rows):
    output = {}
    for mode in ("recent_only", "hybrid"):
        subset = [row for row in rows if row["mode"] == mode]
        valid = [row for row in subset if "error" not in row]
        categories = defaultdict(list)
        for row in valid:
            categories[str(row["category"])].append(row["official_score"])
        def mean(field):
            values = [r[field] for r in valid if r.get(field) is not None]
            return statistics.mean(values) if values else None
        output[mode] = {
            "attempted": len(subset), "completed": len(valid),
            "errors": len(subset) - len(valid),
            "mean_official_qa_score": mean("official_score"),
            "category_scores": {key: {"count": len(values),
                "mean": statistics.mean(values)} for key, values in categories.items()},
            "mean_prompt_token_upper_bound": mean("prompt_token_upper_bound"),
            "mean_generation_ms": mean("generation_ms"),
            "mean_context_build_ms": mean("context_build_ms"),
            "mean_retrieval_ms": mean("retrieval_ms"),
            "mean_prompt_evidence_precision": mean("prompt_evidence_precision"),
            "mean_prompt_evidence_recall": mean("prompt_evidence_recall"),
            "mean_actual_input_tokens": mean("actual_input_tokens"),
            "mean_actual_output_tokens": mean("actual_output_tokens"),
        }
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path,
                        default=Path("/Users/amitoj/Developer/AITutor"))
    parser.add_argument("--dataset", type=Path, default=DATA_ROOT / "locomo10.json")
    parser.add_argument("--scorer", type=Path, default=DATA_ROOT / "upstream_evaluation.py")
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="qwen2.5-1.5b-instruct")
    parser.add_argument("--embedding-model", default="text-embedding-nomic-embed-text-v1.5")
    parser.add_argument("--conversation-limit", type=int, default=0)
    parser.add_argument("--questions-per-category", type=int, default=0)
    parser.add_argument("--budget", type=int, default=2800)
    parser.add_argument("--cutoff", type=float, default=0.6)
    parser.add_argument("--max-tokens", type=int, default=500)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.conversation_limit < 0 or args.questions_per_category < 0:
        parser.error("Subset limits must be non-negative; zero means all")
    if urlparse(args.base_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("Inference must use a local loopback server")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = args.output or ROOT / "benchmark_outputs" / "official_locomo" / stamp
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.app_root))
    import chromadb
    import httpx
    from backend.models.chat import Message
    from backend.memory.semantic_chat import SemanticChatMemory
    from backend.memory.semantic_chat import token_upper_bound
    from backend.services.chat_service import ChatService

    scorer = load_official_scorer(args.scorer)
    dataset = json.loads(args.dataset.read_text())
    selected_samples = dataset[:args.conversation_limit] if args.conversation_limit else dataset
    manifest = {
        "dataset_source": SOURCE_URL, "dataset_sha256": digest(args.dataset),
        "scorer_sha256": digest(args.scorer), "started_utc": stamp,
        "settings": {key: str(value) if isinstance(value, Path) else value
                     for key, value in vars(args).items()},
        "scope": "official dataset subset" if args.conversation_limit or
            args.questions_per_category else "full official dataset QA",
        "scoring": "Upstream eval_question_answering: stemmed F1 for categories 1-4; upstream abstention rule for 5",
        "memory_policy": "Only source dialogue and supplied image captions; no QA or predictions indexed; no generated feedback",
        "adaptation": "Both conversation speakers represented as user records with explicit speaker names and session dates; text-only; no image download",
        "protocol": "Offline local tutor adaptation, not an exact reproduction of the paper's models or prompts",
        "baseline_note": "Both modes reuse the application's context builder, including its chronological outline when triggered. recent_only disables semantic retrieval only.",
        "scope_counts": {"dataset_conversations": len(dataset),
            "dataset_questions": sum(len(s["qa"]) for s in dataset),
            "selected_conversations": len(selected_samples),
            "selected_questions": sum(len(select_questions(s["qa"], args.questions_per_category))
                                      for s in selected_samples)},
        "app_source_hashes": {name: digest(args.app_root / name) for name in (
            "backend/memory/semantic_chat.py", "backend/services/chat_service.py")},
        "selected_questions": {s["sample_id"]: [i for i, _ in
            select_questions(s["qa"], args.questions_per_category)] for s in selected_samples},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("Output:", out, flush=True)
    client = chromadb.PersistentClient(path=str(out / "test_chroma"))
    rows = []
    jsonl = out / "predictions.jsonl"
    def checkpoint():
        summary = {"scope": manifest["scope"], "source": SOURCE_URL,
                   "results": summarize(rows), "completed": False}
        (out / "summary.json").write_text(json.dumps(summary, indent=2))
    with httpx.Client(timeout=180, trust_env=False) as http:
        response = http.get(args.base_url + "/models")
        response.raise_for_status()
        for sample in selected_samples:
            history = conversation_messages(sample, Message)
            repo = TestRepository(client, history)
            memory = SemanticChatMemory(repo, args.base_url, args.embedding_model)
            started = time.perf_counter()
            memory.sync(history[0].user_id)
            print(f'Indexed {sample["sample_id"]}: {len(history)} turns in '
                  f'{time.perf_counter()-started:.1f}s', flush=True)
            for qa_index, qa in select_questions(sample["qa"], args.questions_per_category):
                for mode in ("recent_only", "hybrid"):
                    row = {"sample_id": sample["sample_id"], "qa_index": qa_index,
                           "mode": mode, "question": qa["question"],
                           "reference_answer": qa.get("answer"), "category": qa["category"],
                           "gold_evidence": qa.get("evidence", [])}
                    try:
                        service = ChatService.__new__(ChatService)
                        service._repository = repo
                        service._semantic_memory = memory if mode == "hybrid" else None
                        task_instruction = (
                            "\nAnswer the question about the provided conversation with "
                            "only a short answer, no explanation. Preserve dates and names. "
                            "If not supported, answer: No information available.")
                        service._prompt_token_budget = args.budget - len(task_instruction.encode())
                        service._memory_min_similarity = args.cutoff
                        question = Message(id=f'question-{qa_index}',
                            chat_id=sample["sample_id"], user_id=history[0].user_id,
                            session_id="evaluation", role="user", content=qa["question"],
                            timestamp=history[-1].timestamp + timedelta(days=1))
                        before = time.perf_counter()
                        messages, system = service._prepare_context(question)
                        trace = question.memory_trace
                        row["context_build_ms"] = (time.perf_counter()-before)*1000
                        # Same task instruction and decoding settings for both modes.
                        system += task_instruction
                        request = {"model": args.model, "temperature": 0.1,
                            "seed": 42, "max_tokens": args.max_tokens, "stream": False,
                            "messages": [{"role": "system", "content": system}] +
                                [{"role": m.role, "content": m.content} for m in messages]}
                        row["request_sha256"] = hashlib.sha256(
                            json.dumps(request, sort_keys=True).encode()).hexdigest()
                        before = time.perf_counter()
                        answer = http.post(args.base_url + "/chat/completions", json=request)
                        answer.raise_for_status()
                        result = answer.json()
                        row["generation_ms"] = (time.perf_counter()-before)*1000
                        row["prediction"] = result["choices"][0]["message"]["content"].strip()
                        row["finish_reason"] = result["choices"][0].get("finish_reason")
                        usage = result.get("usage", {})
                        row["actual_input_tokens"] = usage.get("prompt_tokens")
                        row["actual_output_tokens"] = usage.get("completion_tokens")
                        scored = dict(qa, answer=qa.get("answer", ""), prediction=row["prediction"])
                        row["official_score"] = float(scorer["eval_question_answering"](
                            [scored], eval_key="prediction")[0][0])
                        retrieved = trace.get("retrieved_memories", [])
                        included = set(trace.get("history_message_ids", [])) | set(
                            trace.get("conversation_outline_message_ids", [])) | {
                            item["id"] for item in retrieved if item.get("included_in_prompt")}
                        ids = [item.split("::", 1)[-1] for item in included]
                        metrics = evidence_metrics(ids, qa.get("evidence", []))
                        row["prompt_evidence_precision"] = metrics["precision"]
                        row["prompt_evidence_recall"] = metrics["recall"]
                        row["evidence_metric_note"] = "Message-ID coverage; selected excerpts may omit relevant words. Extra diagnostic, not official answer score."
                        row["retrieval_ms"] = trace.get("retrieval_latency_ms")
                        row["prompt_token_upper_bound"] = token_upper_bound(system) + sum(
                            token_upper_bound(m.content) for m in messages)
                        row["configured_input_budget"] = args.budget
                        row["memory_trace"] = trace
                        print(f'{sample["sample_id"]} Q{qa_index} cat={qa["category"]} '
                              f'{mode} score={row["official_score"]:.3f}', flush=True)
                    except Exception as error:
                        row["error"] = f"{type(error).__name__}: {error}"
                        print(row["error"], flush=True)
                    rows.append(row)
                    with jsonl.open("a") as handle:
                        handle.write(json.dumps(row) + "\n")
                    checkpoint()
    summary = json.loads((out / "summary.json").read_text())
    summary["completed"] = True
    summary["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    report = ["# Local Tutor Evaluation on Official LoCoMo Data", "",
              "Scope: " + manifest["scope"], "",
              "This is a local tutor adaptation using upstream QA scoring, not a published-paper reproduction.",
              "Predictions never enter test memory. Category 5 uses the upstream phrase-based abstention rule.", "",
              "| Mode | Completed | Mean QA score | Mean generation ms |", "|---|---:|---:|---:|"]
    for mode, result in summary["results"].items():
        report.append(f'| {mode} | {result["completed"]} | '
                      f'{result["mean_official_qa_score"]} | {result["mean_generation_ms"]} |')
    report.extend(["", "See manifest.json for settings and source hashes; predictions.jsonl for every answer, reference and retrieval trace.",
                   "Evidence coverage and timing are additional diagnostics. Failures remain in predictions.jsonl and error counts."])
    (out / "report.md").write_text("\n".join(report) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
