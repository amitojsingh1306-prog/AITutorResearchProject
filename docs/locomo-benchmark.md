# LoCoMo-Style Benchmark Demo

This project uses LoCoMo as the evaluation inspiration for long-term memory
behavior. The benchmark checks whether the tutor can retrieve earlier user
facts, confusion points, goals, stale memories, and deleted memories.

## Run Command

```bash
cd /Users/amitoj/Desktop/ChatBotTutorAI/AITutor
../.venv/bin/python scripts/run_locomo_benchmark.py
```

## Output Files

```text
benchmark_outputs/locomo/locomo_benchmark_report.md
benchmark_outputs/locomo/locomo_benchmark_report.json
```

## Current Result

```text
Total cases: 5
Passed cases: 5
Recall@3: 1.0
Average retrieval latency: 7.868 ms
P95 retrieval latency: 8.509 ms
Average top cosine similarity: 0.4175
Average top confidence score: 0.7787
Delete handling passed: True
```

## What To Say

LoCoMo is not used as a database or model. It is used as the benchmark pattern.
We created a local test conversation, embedded it into Chroma, and then tested
whether memory questions retrieve the correct earlier information.

The benchmark demonstrates:

- Recall accuracy: earlier user facts are retrieved correctly.
- Semantic retrieval: dense embeddings and cosine similarity rank memories.
- Retrieval latency: each search reports how long retrieval took.
- Confidence score: similarity and query overlap are combined into a score.
- Token buffer: only memory that fits the budget is selected.
- Stale memory: older memory is flagged instead of blindly trusted.
- Delete handling: deleted embeddings stop appearing in retrieval results.

This is a local-only responsible AI evaluation. It does not call an outside API.
