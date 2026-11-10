# Evaluation explained

## What was tested

We tested whether the current context builder supplies useful conversation evidence to local Qwen. This run calls the production context builder and the real local model; it is not a full frontend/FastAPI end-to-end benchmark.

The fixed subset contains 49 distinct questions across 10 official LoCoMo conversations. Four memory modes, with three trials each, produce 588 saved predictions. Repeated trials are not new questions.

## How one test runs

1. Import only the source conversation into a fresh local test namespace. Preserve message IDs, timestamps and supplied captions.
2. Choose buffer, extractive rolling summary, vector retrieval, or graph retrieval. Use the same source conversation, question, input allowance and model settings.
3. Build context with the actual tutor context code. Save the exact model request and which source messages were selected.
4. Ask Qwen through LM Studio on the local machine. Save its answer and request timing. Do not save this prediction back into test memory.
5. Only after generation, give the prediction and withheld reference to the downloaded upstream QA scoring function.
6. Independently rescore saved predictions and verify hashes, source IDs, expected coverage and namespace cleanup.

## What the measurements mean

- Answer F1: normalized, stemmed wording overlap with the reference, for categories 1–4. It is not factual accuracy or memory-retention probability.
- Category 5: the upstream phrase-based abstention score. It checks specified refusal-to-answer phrases; it is not memory recall.
- Cosine similarity: the angle-based similarity used to select vector candidates. It is not a confidence probability and is not a LoCoMo answer score.
- Active vector candidate selection reserves slots for user and assistant records, then applies cosine cutoff, duplicate checks and budget. These are retrieval rules, not calibrated confidence probabilities.
- Evidence-ID precision/recall: how selected source-message IDs overlap with the benchmark evidence IDs. A selected excerpt may still omit the key fact.
- Context time: measured around context construction, including enabled retrieval. Source ingestion is measured separately.
- Generation request time: local HTTP round trip to LM Studio. This is not total UI response time, and it excludes initial corpus ingestion and chat persistence.
- Actual input tokens: reported by LM Studio. The context builder's 6,144-unit allowance is a conservative byte-based bound, not 6,144 tokenizer tokens.

## Current results

| Memory | F1, categories 1–4 | Abstention, category 5 | Context ms | Local generation ms |
|---|---:|---:|---:|---:|
| buffer | 0.0053 | 0.9000 | 70.17 | 1411.72 |
| summary | 0.0098 | 0.8333 | 97.35 | 2370.25 |
| vector | 0.1637 | 0.6000 | 740.07 | 4671.82 |
| graph | 0.0247 | 0.6000 | 426.98 | 4323.04 |

## Actual examples

### conv-26 / question 3 / category 1

Question: What did Caroline research?

Reference: Adoption agencies

Qwen: Caroline researched doing research and readying herself emotionally for her role as an advocate for transgender youth.

Upstream score: 0.0000. Gold evidence IDs: D2:8

### conv-42 / question 1 / category 1

Question: What kind of interests do Joanna and Nate share?

Reference: Watching movies, making desserts

Qwen: Joanna enjoys writing, reading, watching movies, and exploring nature. Nate is a fan of gaming and has shared his love for turtles with Joanna. They both appreciate the calming effect of their respective hobbies on their lives.

Upstream score: 0.5000. Gold evidence IDs: D1:10, D1:11, D1:12, D3:4, D4:9, D10:9, D20:2

### conv-26 / question 0 / category 2

Question: When did Caroline go to the LGBTQ support group?

Reference: 7 May 2023

Qwen: 2023-05-07

Upstream score: 0.0000. Gold evidence IDs: D1:3

### conv-49 / question 4 / category 2

Question: Which hobby did Sam take up in May 2023?

Reference: painting

Qwen: Sam took up painting in May 2023.

Upstream score: 0.2500. Gold evidence IDs: D1:11

### conv-42 / question 88 / category 4

Question: What is one of Joanna's favorite movies?

Reference: "Eternal Sunshineof the Spotless Mind"

Qwen: One of Joanna's favorite movies is "Little Women."

Upstream score: 0.0000. Gold evidence IDs: D1:18, D, D1:20

### conv-44 / question 61 / category 4

Question: Which specific type of bird mesmerizes Andrew?

Reference: Eagles

Qwen: Eagles.

Upstream score: 1.0000. Gold evidence IDs: D1:16

### conv-26 / question 152 / category 5

Question: What did Caroline realize after her charity race?

Reference: (upstream unanswerable case)

Qwen: Caroline realized self-acceptance and how to find support through her charity race for mental health.

Upstream score: 0.0000. Gold evidence IDs: D2:3

### conv-41 / question 152 / category 5

Question: What is John's main focus in international politics?

Reference: (upstream unanswerable case)

Qwen: No information available.

Upstream score: 1.0000. Gold evidence IDs: D1:8

## Interpretation

An audit pass means the saved predictions were scored and counted consistently with the declared protocol. It does not mean Qwen answered every question correctly.
One inspected temporal example predicts 2023-05-07 against reference 7 May 2023 and receives upstream F1 0.0. The dates are equivalent; the score is sensitive to their written format. This qualitative observation does not replace the official score.
Compare modes on this fixed subset only. Do not call a small F1 improvement proof that hallucinations are solved. Inspect wrong entities, dates, unsupported details, missed evidence and unnecessary abstention separately.
The earlier 2,800-unit diagnostic excluded every rolling summary; its summary/buffer equality cannot establish the usefulness of summary memory. The current 6,144-unit run must be read with actual memory-path participation from audit.json.
Latency is descriptive on an active local workstation. Mode order is fixed, model caches are not reset between requests, and the run is not a dedicated throughput benchmark.
The paper-reference row quotes Mem0 Table 1: single-hop F1 .3872, multi-hop .2864, open-domain .4765, temporal .4893 (published percentages divided by 100). Its GPT-4o-mini setup and evaluation scope differ; it excludes adversarial questions. Source: https://arxiv.org/html/2504.19413v1.
Published MemGPT, Mem0 and A-MEM experiments use different systems, models, scoring and budgets. These local baseline scores are not a direct ranking against their published results.

## Code to show the panel

- scripts/run_panel_evaluation.py: selection, source import, context creation, saved requests, local generation and scoring.
- backend/services/chat_service.py: _prepare_context() assembles selected memory into the prompt.
- backend/memory/semantic_chat.py: local embeddings, vector search, candidate filtering and input allowance.
- backend/memory/rolling_summary.py: bounded source excerpts; not a generative summary model.
- backend/memory/graph_memory.py: supported fact extraction, Neo4j source links and graph/keyword retrieval.
- scripts/audit_panel_results.py: independent score and protocol checks.
- scripts/show_evaluation_results.py: tables, worked numerical example and all saved answers.

## One command

```bash
/Users/amitoj/Developer/AITutor/.venv/bin/python /Users/amitoj/Developer/AITutor/scripts/show_evaluation_results.py --answers
```

## Live chat verification

The separate streaming-route check used the actual frontend endpoint with local Qwen/Nomic and fresh storage. It recalled the name, subject, language and preference; accepted a correction to AJ; and stopped recalling the old topic after forgetting. The source was confirmed absent from JSON, MySQL, Chroma and Neo4j. This is an integration test, not a LoCoMo accuracy score.

The first full streaming response took about 51.1 seconds; the later factual recap about 16.0 seconds. These timings include persistence and retrieval. TestClient measured complete responses, not time to first visible token. A separate non-streaming request failed with HTTP 502 after its 60-second model read timeout. That failure is preserved in benchmark_outputs/live_tutor_nonstream_failure.json and has not been fixed.
