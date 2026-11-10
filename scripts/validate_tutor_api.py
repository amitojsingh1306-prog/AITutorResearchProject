"""Targeted API regressions: raw vs structured answer vs temporal normalization.

This is a post-hoc regression experiment, not a fresh full LoCoMo score.
Each worker uses fresh local storage and exits before its database is removed.
"""
import argparse
import ast
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import string
import subprocess
import sys
import time

from locomo_eval_protocol import (
    ANSWER_CONTRACT, TEMPORAL_CONTRACT, RESERVED_BYTES, JSON_CONTRACT,
    calendar_reference, extract_answer, extract_json_answer,
    annotate_relative_dates, isolated_storage,
)


def official_scorer(path):
    import numpy as np
    import regex
    from nltk.stem import PorterStemmer
    wanted = {"normalize_answer", "exact_match_score", "f1_score", "f1", "eval_question_answering"}
    functions = [n for n in ast.parse(path.read_text()).body
                 if isinstance(n, ast.FunctionDef) and n.name in wanted]
    if {f.name for f in functions} != wanted:
        raise ValueError("Unexpected upstream scorer")
    ns = dict(np=np, regex=regex, string=string, Counter=Counter, ps=PorterStemmer())
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), ns)
    return ns


def worker(args):
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    sys.path.insert(0, str(args.app_root))
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.chat import router
    from backend.database.chroma_repository import ChromaChatRepository
    from backend.llm.groq_client import GroqClient
    from backend.memory.semantic_chat import SemanticChatMemory, token_upper_bound
    from backend.models.chat import Message, ChatSummary
    from backend.services.chat_service import ChatService

    sample = json.loads(args.dataset.read_text())[0]
    qa = sample["qa"][args.qa_index]
    history = []
    conversation = sample["conversation"]
    for session in sorted((k for k in conversation if re.fullmatch(r"session_\d+", k)),
                          key=lambda k: int(k.split("_")[1])):
        date_text = conversation[session + "_date_time"]
        date = datetime.strptime(date_text, "%I:%M %p on %d %B, %Y").replace(tzinfo=timezone.utc)
        for offset, turn in enumerate(conversation[session]):
            text = f'[{date_text}] {turn["speaker"]}: {turn["text"]}'
            if turn.get("blip_caption"):
                text += " [Provided image caption: " + str(turn["blip_caption"]) + "]"
            history.append(Message(id=sample["sample_id"]+"::"+turn["dia_id"],
                chat_id=sample["sample_id"], user_id="isolated-api-audit", session_id=session,
                role="user", content=text, timestamp=date + timedelta(seconds=offset)))

    class EvaluationService(ChatService):
        def _prepare_context(self, message):
            messages, system = super()._prepare_context(message)
            hints = []
            if args.mode.startswith("json"):
                system += JSON_CONTRACT
            elif args.mode != "raw":
                system += ANSWER_CONTRACT
            if args.mode.endswith("temporal"):
                system += TEMPORAL_CONTRACT
                trace = message.memory_trace
                sources = [(m.content, m.timestamp) for m in messages[:-1]]
                sources += [(item.get("prompt_excerpt", ""), item["timestamp"])
                            for item in trace.get("retrieved_memories", [])
                            if item.get("included_in_prompt")]
                if args.mode == "json_temporal":
                    messages = [m.model_copy(update={"content": annotate_relative_dates(m.content, m.timestamp)})
                                for m in messages[:-1]] + messages[-1:]
                    for item in trace.get("retrieved_memories", []):
                        if not item.get("included_in_prompt"):
                            continue
                        original = item.get("prompt_excerpt", "")
                        annotated = annotate_relative_dates(original, item["timestamp"])
                        system = system.replace(json.dumps(original), json.dumps(annotated))
                for text, timestamp in sources:
                    hint = calendar_reference(text, timestamp)
                    if hint and hint not in hints:
                        addition = "\n" + hint
                        if token_upper_bound(system + addition) + sum(
                                token_upper_bound(m.content) for m in messages) <= 2800:
                            hints.append(hint)
                            system += addition
            total = token_upper_bound(system) + sum(token_upper_bound(m.content) for m in messages)
            if total > 2800:
                raise ValueError("Evaluation instructions exceed total context budget")
            message.memory_trace.update({"evaluation_mode": args.mode,
                "evaluation_calendar_references": hints,
                "evaluation_total_input_upper_bound": total})
            return messages, system

    repo = ChromaChatRepository(args.storage)
    now = datetime.now(timezone.utc)
    repo.save_chat(ChatSummary(id=sample["sample_id"], title="Isolated evaluation",
        user_id="isolated-api-audit", session_id="evaluation", created_at=now, updated_at=now))
    repo._write_json_file(repo._message_file, {m.id: m.model_dump_json() for m in history})
    memory = SemanticChatMemory(repo, "http://127.0.0.1:1234/v1",
                               "text-embedding-nomic-embed-text-v1.5")
    repo.semantic_memory = memory
    memory.sync("isolated-api-audit")
    llm = GroqClient(api_key="local", model="qwen2.5-1.5b-instruct",
        base_url="http://127.0.0.1:1234/v1", temperature=.1, num_predict=128, timeout_seconds=180)
    if args.mode.startswith("json"):
        class StructuredClient:
            def generate_reply(self, messages, system_prompt=None):
                import httpx
                schema = {"type": "object", "properties": {
                    "answer": {"type": "string"}, "explanation": {"type": "string"}},
                    "required": ["answer", "explanation"], "additionalProperties": False}
                result = httpx.post("http://127.0.0.1:1234/v1/chat/completions", json={
                    "model": "qwen2.5-1.5b-instruct", "temperature": .1,
                    "max_tokens": 128, "stream": False,
                    "messages": [{"role": "system", "content": system_prompt}] +
                        [{"role": m.role, "content": m.content} for m in messages],
                    "response_format": {"type": "json_schema", "json_schema": {
                        "name": "evaluation_answer", "strict": True, "schema": schema}}},
                    timeout=180, trust_env=False)
                result.raise_for_status()
                payload = result.json()
                self.finish_reason = payload["choices"][0].get("finish_reason")
                return payload["choices"][0]["message"]["content"]
        llm = StructuredClient()
    app = FastAPI()
    app.include_router(router)
    # Identical evidence-selection budget in every mode reserves room for instructions.
    app.state.chat_service = EvaluationService(repo, llm, semantic_memory=memory,
        prompt_token_budget=2800-RESERVED_BYTES, memory_min_similarity=.6)
    before = time.perf_counter()
    with TestClient(app) as api:
        response = api.post(f'/chat/{sample["sample_id"]}/message',
            headers={"X-User-Id": "isolated-api-audit"}, json={"content": qa["question"]})
        response.raise_for_status()
        result = response.json()
    raw = result["assistant_message"]["content"]
    answer, parse_status = (extract_json_answer(raw) if args.mode.startswith("json") else
                            extract_answer(raw) if args.mode != "raw" else (raw, "not_requested"))
    score = official_scorer(args.scorer)["eval_question_answering"]
    raw_f1 = float(score([dict(qa, prediction=raw)])[0][0])
    core_f1 = float(score([dict(qa, prediction=answer)])[0][0])
    case = {"qa_index": args.qa_index, "mode": args.mode, "question": qa["question"],
        "reference": qa["answer"], "raw_response": raw, "extracted_answer": answer,
        "finish_reason": getattr(llm, "finish_reason", None),
        "parse_status": parse_status, "raw_upstream_f1": raw_f1,
        "boundary_answer_upstream_f1": core_f1, "http_status": response.status_code,
        "latency_ms": (time.perf_counter()-before)*1000,
        "memory_trace": result["assistant_message"]["memory_trace"],
        "source_turns": len(history), "source_only_seed": True}
    args.result.write_text(json.dumps(case, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("/Users/amitoj/Developer/AITutor/benchmark_data/locomo/locomo10.json"))
    parser.add_argument("--scorer", type=Path, default=Path("/Users/amitoj/Developer/AITutor/benchmark_data/locomo/upstream_evaluation.py"))
    parser.add_argument("--app-root", type=Path, default=Path("/Users/amitoj/Developer/AITutor"))
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--storage", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--qa-index", type=int)
    parser.add_argument("--mode", choices=("raw", "tagged", "tagged_temporal", "json", "json_temporal"))
    parser.add_argument("--modes", default="raw,json,json_temporal")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    out = args.output or Path("/private/tmp") / ("tutor-evaluation-fixes-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    out.mkdir(parents=True, exist_ok=False)
    snapshot = out / "runner_snapshot.py"
    shutil.copyfile(__file__, snapshot)
    shutil.copyfile(Path(__file__).with_name("locomo_eval_protocol.py"), out / "locomo_eval_protocol.py")
    report = {"scope": "Targeted post-hoc regression checks, not an unbiased benchmark estimate",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256(Path(__file__).with_name("locomo_eval_protocol.py").read_bytes()).hexdigest(),
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "scorer_sha256": hashlib.sha256(args.scorer.read_bytes()).hexdigest(),
        "protocol": "Preserve raw F1; additionally score one declared answer boundary. No reference-dependent extraction.",
        "generation": {"temperature": .1, "max_tokens": 128, "total_budget": 2800,
                       "common_evidence_budget": 2800-RESERVED_BYTES}, "cases": []}
    print("Output:", out, flush=True)
    modes = args.modes.split(",")
    if any(mode not in {"raw", "tagged", "tagged_temporal", "json", "json_temporal"} for mode in modes):
        parser.error("Unknown evaluation mode")
    for index in (0, 82):
        for mode in modes:
            case_path = out / f"case-{index}-{mode}.json"
            with isolated_storage() as storage:
                proc = subprocess.run([sys.executable, str(snapshot), "--worker", "--storage", str(storage),
                    "--result", str(case_path), "--dataset", str(args.dataset), "--scorer", str(args.scorer),
                    "--app-root", str(args.app_root), "--qa-index", str(index), "--mode", mode],
                    capture_output=True, text=True, timeout=240)
                (out / f"case-{index}-{mode}.log").write_text(proc.stdout + proc.stderr)
                if proc.returncode:
                    raise RuntimeError(f"Worker failed; see case-{index}-{mode}.log")
                case = json.loads(case_path.read_text())
            case["temporary_database_removed"] = not storage.exists()
            report["cases"].append(case)
            (out / "report.json").write_text(json.dumps(report, indent=2))
            print(index, mode, "answer:", case["extracted_answer"],
                  "raw F1:", case["raw_upstream_f1"],
                  "boundary F1:", case["boundary_answer_upstream_f1"], flush=True)
    report["completed"] = True
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print("Completed:", out, flush=True)


if __name__ == "__main__":
    main()
