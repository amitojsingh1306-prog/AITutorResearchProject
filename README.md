# Hybrid Memory Benchmark for a Local Student Tutor

A local tutor and a comparison of conversation buffer, extractive rolling summary,
vector memory and graph memory. Qwen generates answers; memory supplies evidence.
This project does not train Qwen on conversation records or on embeddings.

## Run

The canonical checkout is `/Users/amitoj/Developer/AITutor`. The Desktop
`ChatBotTutorAI/AITutor` entry points to that checkout, not an independent version.

```sh
cd /Users/amitoj/Developer/AITutor
.venv/bin/python scripts/start_local.py
```

Open `http://127.0.0.1:5173`. The launcher checks the project's MySQL and Neo4j,
then starts FastAPI and React. LM Studio must serve the local Qwen and Nomic
models. Run `scripts/panel_preflight.py` before the demonstration.

## Current architecture

1. React sends a message or image to FastAPI.
2. The backend validates ownership, saves the source in JSON and synchronizes it to local MySQL when enabled.
3. The selected memory mode reads recent history and additional evidence.
4. The backend assembles bounded text context and sends it to local Qwen through LM Studio.
5. React displays the response; the backend saves it and updates derived memory.
6. Explicit edits, deletions and forgetting reconcile source and derived stores.

JSON is the backend's working conversation memory and synchronizes to local MySQL.
Qwen only receives assembled text through LM Studio. JSON files include filled common
session blueprints. Chroma holds actual Nomic vectors and linked text. Neo4j
holds source-linked learner facts and original-user-message nodes. Nomic and
Qwen are different models; Qwen receives retrieved text, not Nomic vectors.

## Four memory configurations

| Mode | Evidence added to recent context |
|---|---|
| `buffer` | None |
| `summary` | Bounded older source excerpts from the current chat |
| `vector` | Older user-scoped messages retrieved through Nomic and Chroma |
| `graph` | Supported learner facts and graph-backed keyword source fallback |

`hybrid` combines these paths. Summary is extractive, not LLM paraphrasing.
Graph source fallback is lexical retrieval over source nodes, not vector search
or a claim of unrestricted multi-hop reasoning. Memory selection is backend
logic; the application does not require five agents to answer simultaneously.

## Demonstration and evidence

```sh
.venv/bin/python scripts/panel_preflight.py
.venv/bin/python scripts/panel_demo.py
.venv/bin/python scripts/inspect_memory.py --user YOUR_FRONTEND_USER_ID --follow
```

The demo uses isolated example records and real local services. It leaves
ordinary conversations untouched and removes its test records afterward.
The inspector reads only the specified learner's chat. Similarity values are
retrieval scores, not probabilities that an answer is correct.

```sh
.venv/bin/python scripts/run_panel_evaluation.py --conversation-limit 10 --repeats 3
```

This compares four modes using the first available question per category in
each official LoCoMo conversation: 49 unique questions, three trials per mode,
588 planned predictions. It is a selected-subset adaptation, not the full 1,986
questions or a reproduction of published paper scores. The current production
context builder is invoked directly; full API storage/image/deletion behaviour
is tested separately. References and generated answers never enter test memory.

Reports, raw predictions, source hashes, settings and cleanup receipts are saved
under `benchmark_outputs/panel/`. Do not compare a partial run's averages between
modes with unequal completed questions. Do not present the earlier historical
benchmark as a measurement of newer code.

For the demonstration order, code locations and claim boundaries, read
[Panel guide](docs/panel-guide.md). Fresh results and recommendations are
available in `benchmark_outputs/panel/20261108_live_budget/report.md` and its accompanying audit.

## Memory control and limits

Examples: `Forget my name.`, `Forget about recursion.`, `Forget this chat.` and
`Update my name to AJ.`. Ambiguous commands ask for clarification. FastAPI also
provides PATCH/DELETE message routes and DELETE chat. See
[Update and forgetting](docs/update-delete-forgetting.md).

Tracked sessions expire after one hour of inactivity. Cross-chat recall only
applies while records remain retained. Original external files, backups, logs
and exports are outside active-store deletion. Identity headers are a local
prototype mechanism, not production authentication. Loopback model URLs are
enforced by default; this is not a complete privacy/security certification.

Images use local Tesseract OCR followed by text-based Qwen generation; general
visual reasoning is not implemented. The small model can still make factual or
reasoning errors even with relevant memory.

## Dependencies and checks

Use the existing `.venv`. `backend/requirements.txt` contains runtime packages;
`backend/requirements-evaluation.txt` adds scoring/test packages. OCR additionally
requires local Tesseract and the English weights in `ocr_models/`. Model weights
must be available in LM Studio. Private service credentials stay under ignored
`.local/` files and must not be displayed or committed.

Run the automated checks with:

```sh
.venv/bin/python -B -m pytest backend/tests scripts/test_locomo_eval_protocol.py scripts/test_official_locomo.py -q
```

The checks cover memory, routes, OCR, scoring and explicit legacy compatibility.
They do not imply that the active tutor uses the old multi-agent pipeline.
Real local-service integration and model answer quality are separate checks.
