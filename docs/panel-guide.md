# Panel demonstration guide

## What the project demonstrates

The problem is continuity: a local tutor should recall a learner's goals,
preferences, difficulties and completed topics without putting every saved
message into every prompt. The experiment compares four ways of supplying
memory, and records the cost and failure cases. This is a systems comparison,
not a newly trained language model or a claim to outperform commercial tutors.

## Before the review

```sh
cd /Users/amitoj/Developer/AITutor
.venv/bin/python scripts/panel_preflight.py
```

Keep the frontend, local model server and local databases running. Use only a
clean demonstration chat; avoid opening your existing private conversations.
Keep `deliverables/panel/READINESS.md`, the complete comparison report and one
saved failure available. Demonstrate with actual evidence rather than guessing
which subsystem caused an answer.

## An eight and a half minute presentation

| Time | Show | Explain |
|---|---|---|
| 0:00–0:45 | Problem | A fluent tutor can still forget the learner |
| 0:45–1:30 | Four memory methods | Compare buffer, summary, vector and graph |
| 1:30–2:45 | Numbered workflow | Storage supplies evidence; Qwen generates text |
| 2:45–3:45 | Dataset and protocol | Same selected questions, three trials, references excluded |
| 3:45–5:45 | Clean tutor example | Save a topic and difficulty, then ask in a new chat |
| 5:45–6:45 | Results | Separate F1, abstention, context cost and generation time |
| 6:45–7:45 | Update and forgetting | Remove active evidence, not merely ask the model to forget |
| 7:45–8:30 | Findings and limits | State where each memory method fails and what to improve |

Leave the remaining team time as a buffer for questions. Do not narrate every
box, file or decimal during the main explanation. Keep code ready for follow-up.

## Clean example

Use the following statements in a new chat:

1. My name is Amitoj. I'm learning binary search in Python. I prefer short explanations using numbered steps.
2. I keep confusing low, high, and mid. Remember that this is my main difficulty.
3. My goal is to implement binary search correctly in Python.
4. I have completed arrays.

Open another chat under the same learner identity. Ask what algorithm you are
learning and what you struggle with. Show the actual answer and source trace.
Then use `Update my name to AJ.`, ask your name, use `Forget my name.`, and ask
again. Source removal is the important proof; a polite acknowledgement is not.

For an automated isolated version with saved answers and independently
recomputed cosine values:

```sh
.venv/bin/python scripts/panel_demo.py
```

This is a custom tutor scenario, not an official LoCoMo score. Its term-presence
checks are diagnostics; read the whole answer before claiming correctness.

## Explain the measurements

Start with the question, supporting source and generated answer. Then explain
the numbers in relation to those items. Answer F1 measures normalised word
overlap with a held-out reference. It is not the proportion of all memories
remembered. Category 5 tests abstention using the downloaded scorer's phrase
rule; it is reported separately. A correct paraphrase can have lower overlap,
and an incorrect date can receive partial overlap credit.

Cosine similarity ranks proximity between Nomic vectors. A cutoff such as 0.60
is a retrieval policy, not a 60% confidence claim. User-source candidate slots,
the cutoff, duplicate removal and the input allowance jointly determine which
records reach Qwen. Two similar scores do not prove either fact is true.

Generation timing is the local LM Studio completion request, while context
timing covers evidence preparation. The full API demo request also includes
storage and other work. Actual input tokens come from model usage when saved;
the context builder's named token upper bound uses UTF-8 bytes plus allowances.

## Exact code to open when asked

| Question | Code location |
|---|---|
| How is the backend wired to LM Studio? | `backend/main.py` local client construction; `backend/llm/groq_client.py` completion transport |
| Why is that transport named Groq? | Historical adapter name; the active URL is local LM Studio and no Groq service is selected |
| Where are remote model URLs blocked? | `backend/utils/local_endpoints.py`; invoked before startup |
| What actually enters Qwen's prompt? | `ChatService._prepare_context` in `backend/services/chat_service.py` |
| How are embeddings stored and searched? | `SemanticChatMemory.sync` and `retrieve` in `backend/memory/semantic_chat.py` |
| How is cosine calculated? | Chroma cosine index; `scripts/panel_demo.py` independently recomputes dot product and vector norms |
| Where is rolling summary implemented? | `RollingSummary.context` in `backend/memory/rolling_summary.py` |
| Where are graph relationships queried? | `Neo4jMemory.sync` and `retrieve` in `backend/memory/graph_memory.py` |
| How does JSON synchronize to MySQL? | `backend/database/mysql_repository.py`, `mysql_store.py` and `factory.py`; pending snapshots allow retry, and Qwen only receives assembled text |
| Where are updates and forgetting implemented? | `backend/api/chat.py` routes and `backend/memory/mutations.py` |
| How is retention enforced? | `SessionMemory.expire` and the backend cleanup worker |
| How do images work? | `backend/api/chat.py` image upload; `backend/ocr/local_ocr.py` |
| Where is evaluation? | `scripts/run_panel_evaluation.py`; source/scorer hashes and every prediction in its output folder |

## Claim boundaries

- Four selectable memory configurations are implemented. They have different evidence sources and failure modes.
- Summary is an extractive current-chat baseline. Cross-chat retrieval in the hybrid uses vector and graph paths.
- A graph path can link a study topic to a difficulty. This does not prove universal multi-hop reasoning.
- The official dataset adaptation uses a fixed selected subset. A custom screenshot example is not LoCoMo.
- Local inference reduces transmission to external model services. It does not prove complete privacy, authentication or forensic erasure.
- One-hour inactivity forgetting is intentional. Do not promise indefinite memory across sessions.
- Generated answers are not indexed during evaluation. Normal chat may retain assistant replies, so role and provenance still matter.
- Explainability means source evidence and selection traces, not access to the model's internal reasoning.
- Distinguish the 70 current-path checks and 44 legacy-agent compatibility checks. Both pass, but only the former describe the active memory path; real local-service checks are separate.

## Current checks

```sh
.venv/bin/python -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_panel_evaluation.py backend/tests/test_panel_privacy.py \
  backend/tests/test_rolling_graph.py backend/tests/test_memory_mutations.py \
  backend/tests/test_image_upload.py backend/tests/test_session_memory.py \
  backend/tests/test_image_memory.py backend/tests/test_local_ocr.py \
  scripts/test_locomo_eval_protocol.py scripts/test_official_locomo.py
```

Use the final readiness report for the latest outcome. Real-store checks and
Qwen observations are separate from these deterministic automated checks.

The full suite can be run with `.venv/bin/python -B -m pytest -q backend/tests scripts/test_locomo_eval_protocol.py scripts/test_official_locomo.py`. The legacy fixture uses an explicit adapter rather than changing production routing or removing assertions.
