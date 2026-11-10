# Research papers and our actual implementation

This guide maps research ideas to the project code. It does not claim that our system fully reproduces MemGPT, Mem0 or A-MEM. Read the source files directly with the viewer; no duplicate backend implementation is stored here.

## Start here

```bash
cd /Users/amitoj/Developer/AITutor
.venv/bin/python -B verification/paper_implementations/show_paper_code.py
```

Choose one topic with `--paper memgpt`, `--paper rag`, `--paper summary`, `--paper mem0`, `--paper amem`, `--paper locomo` or `--paper engineering`. Add `--full` to print complete functions. The viewer only reads code. It does not call LM Studio, mutate databases or rerun a benchmark.

## Research connection versus reproduction

The four required configurations are buffer, summary, vector and graph. They are not four papers or four autonomous agents. The papers inform design choices; the code below is our implementation. Source-level correspondence does not establish a claim that a particular function was written only after a particular paper was read.

## MemGPT: bounded context and external memory

**Status:** Inspired by the memory-tier idea; not a full MemGPT implementation.

The backend keeps selected recent messages and older evidence within a finite prompt allowance. It does not implement model-controlled paging or the full MemGPT operating-system abstraction.

Paper: https://arxiv.org/abs/2310.08560

- `backend/services/chat_service.py` - code around `history_budget =`
- `backend/memory/semantic_chat.py` - `token_upper_bound()`

### Show the implementation

```bash
.venv/bin/python -B verification/paper_implementations/show_paper_code.py --paper memgpt
```

### Demonstrate behavior

```bash
.venv/bin/python -B verification/verify_context.py
```

**What you can say:** The backend keeps selected recent messages and older evidence within a finite prompt allowance. It does not implement model-controlled paging or the full MemGPT operating-system abstraction.

**What this does not prove:** The input estimator is a conservative UTF-8 byte bound, not exact tokenizer counting. There is no universal 70-percent paging rule here.

## RAG: retrieve source text before generation

**Status:** A local retrieval-augmented pipeline; not the original jointly trained RAG model.

Nomic embeds text, Chroma compares query and stored vectors, and Python sends the selected original words to Qwen. Qwen never reads Nomic vectors directly.

Paper: https://arxiv.org/abs/2005.11401

- `backend/memory/semantic_chat.py` - `SemanticChatMemory.embed()`
- `backend/memory/semantic_chat.py` - `SemanticChatMemory.retrieve()`
- `backend/services/chat_service.py` - code around `below_similarity_threshold`

### Show the implementation

```bash
.venv/bin/python -B verification/paper_implementations/show_paper_code.py --paper rag
```

### Demonstrate behavior

```bash
.venv/bin/python -B verification/verify_nomic_embeds.py
.venv/bin/python -B verification/verify_chroma_storage.py
.venv/bin/python -B verification/verify_cosine.py
.venv/bin/python -B verification/verify_context.py
```

**What you can say:** Nomic embeds text, Chroma compares query and stored vectors, and Python sends the selected original words to Qwen. Qwen never reads Nomic vectors directly.

**What this does not prove:** Similarity is relevance, not correctness. A fetched candidate can be excluded by the cutoff or already included through recent history.

## Summary memory: bounded older excerpts

**Status:** Our extractive summary baseline. Not a complete published memory system.

Older learner excerpts are selected under a byte budget, while recent turns stay separate. Source IDs and a source-content signature support refresh after edits.

Paper: https://arxiv.org/abs/2402.17753

- `backend/memory/rolling_summary.py` - `RollingSummary.context()`

### Show the implementation

```bash
.venv/bin/python -B verification/paper_implementations/show_paper_code.py --paper summary
```

### Demonstrate behavior

```bash
.venv/bin/python -B verification/verify_rolling_summary.py
```

**What you can say:** Older learner excerpts are selected under a byte budget, while recent turns stay separate. Source IDs and a source-content signature support refresh after edits.

**What this does not prove:** This copies and truncates source excerpts. Asking Qwen to summarize the chat is a different operation. It may omit important older facts.

## Mem0 connection: updating and removing remembered information

**Status:** Our mutation implementation addresses a related design concern; it does not reproduce Mem0 extraction/consolidation.

Supported corrections and forgetting requests trigger backend operations on source and derived records. The model saying it forgot is not sufficient.

Paper: https://arxiv.org/abs/2504.19413

- `backend/memory/mutations.py` - `MemoryMutations.control()`
- `backend/memory/mutations.py` - `MemoryMutations._apply()`

### Show the implementation

```bash
.venv/bin/python -B verification/paper_implementations/show_paper_code.py --paper mem0
```

### Demonstrate behavior

```bash
.venv/bin/python -B verification/verify_mysql.py
.venv/bin/python -B verification/verify_neo4j.py
```

**What you can say:** Supported corrections and forgetting requests trigger backend operations on source and derived records. The model saying it forgot is not sufficient.

**What this does not prove:** The database checks cover selected mutation paths in isolated namespaces. They do not prove arbitrary natural-language deletion or all concurrency cases. We do not have separately retained facts surviving the current whole-session inactivity expiry.

## A-MEM connection: linked memories and source evidence

**Status:** A restricted rule-based Neo4j implementation; not full A-MEM agentic memory evolution.

Learner assertions, topics and source messages are linked. Supported later statements can deactivate old facts, and the retrieval path returns textual evidence.

Paper: https://arxiv.org/abs/2502.12110

- `backend/memory/graph_memory.py` - `extract_facts()`
- `backend/memory/graph_memory.py` - `Neo4jMemory.retrieve()`

### Show the implementation

```bash
.venv/bin/python -B verification/paper_implementations/show_paper_code.py --paper amem
```

### Demonstrate behavior

```bash
.venv/bin/python -B verification/verify_neo4j.py
```

**What you can say:** Learner assertions, topics and source messages are linked. Supported later statements can deactivate old facts, and the retrieval path returns textual evidence.

**What this does not prove:** Neo4j is our implementation choice, not a requirement of A-MEM. We do not implement unrestricted self-organizing notes, general inference, or permanent fact retention. Topic mentions alone are not learner facts.

## LoCoMo: questions, predictions and upstream scoring

**Status:** Our runner uses released data and downloaded upstream scoring functions.

The runner loads source history, builds context, generates using local Qwen, then scores against held-out references. F1, adversarial abstention, context time and generation request time are separate measurements.

Paper: https://github.com/snap-research/locomo

- `scripts/run_panel_evaluation.py` - code around `row['context_build_ms']`
- `scripts/run_panel_evaluation.py` - `summarize()`
- `benchmark_data/locomo/upstream_evaluation.py` - `f1_score()`
- `benchmark_data/locomo/upstream_evaluation.py` - `eval_question_answering()`

### Show the implementation

```bash
.venv/bin/python -B verification/paper_implementations/show_paper_code.py --paper locomo
```

### Demonstrate behavior

```bash
.venv/bin/python -B verification/locomo_questions/show_questions.py --question 1 --answers
.venv/bin/python -B verification/verify_evaluation.py
```

**What you can say:** The runner loads source history, builds context, generates using local Qwen, then scores against held-out references. F1, adversarial abstention, context time and generation request time are separate measurements.

**What this does not prove:** 49 fixed questions x 4 modes x 3 trials = 588 predictions, not the full dataset. Upstream scorer code was downloaded, not invented by us. Re-scoring saved predictions is not a new model run.

## Supporting application code: SQL, OCR, instructions and retention

**Status:** Engineering support, not a claimed reproduction of a research paper.

JSON stores working records, MySQL keeps recoverable persistence, response blueprints supply instructions, and Tesseract supplies image text. Session expiry is a separate retention policy.

- `backend/database/mysql_repository.py` - `MySQLChatRepository._write_json_file()`
- `backend/services/response_blueprint.py` - `select_template()`
- `backend/memory/session_memory.py` - `SessionMemory._touch()`
- `backend/ocr/local_ocr.py` - code around `class LocalOCR`

### Show the implementation

```bash
.venv/bin/python -B verification/paper_implementations/show_paper_code.py --paper engineering
```

### Demonstrate behavior

```bash
.venv/bin/python -B verification/verify_mysql.py
.venv/bin/python -B verification/verify_blueprint.py
.venv/bin/python -B verification/verify_ocr_blueprint.py
```

**What you can say:** JSON stores working records, MySQL keeps recoverable persistence, response blueprints supply instructions, and Tesseract supplies image text. Session expiry is a separate retention policy.

**What this does not prove:** OCR extracts text rather than visual reasoning. Qwen reads instructions inserted by Python, not JSON files directly. The current timer expires tracked whole sessions after one hour of inactivity.

## Live-review sequence

1. State the paper idea in one sentence.
2. Show the production function with the read-only viewer.
3. Run the relevant existing verification command, if its local services are available.
4. Point to inputs, actual output and source IDs.
5. State the limitation. A component PASS is not a model accuracy score.

Nomic/Qwen demonstrations require LM Studio with the corresponding local model. SQL and Neo4j checks require the local database services and isolated test namespaces. They create and clean test records; do not describe them as read-only. The OCR check requires Tesseract. The evaluation checker re-scores saved data and can refresh audit files. Consult verification/README.md for each check's scope.

## Current retention limitation

Facts extracted into Neo4j do not automatically bypass the one-hour whole-session expiry. Longer-lived confirmed facts would require a separate implemented retention policy, ownership/source tracking and correction/deletion handling. That extension has not been implemented here.
