# High-level design

Project: Hybrid Memory Benchmark for a Local Student Tutor

The tutor compares conversation buffer, extractive rolling summary, vector memory and graph memory. It aims to retrieve relevant, traceable learner history within a bounded prompt and support correction and forgetting. Memory retrieval does not eliminate model reasoning errors.

## Connected runtime

1. React sends the message, learner ID and chat ID to local FastAPI on port 8000.
2. ChatService checks ownership and supported update/forget commands. A mutation follows the backend cleanup path and receives a backend acknowledgement rather than an invented model confirmation.
3. The backend saves ordinary messages in JSON working memory and synchronizes local MySQL. Pending-operation snapshots allow failed synchronization to retry. This coordination is not a distributed atomic transaction.
4. Saved text updates local Nomic embeddings in Chroma and source-supported Neo4j records. For answering, the backend reads recent history and the enabled summary, vector and graph evidence.
5. The backend selects the response blueprint, removes duplicate vector evidence, applies the similarity cutoff and fits selected text into a conservative input allowance. The normal template guides explanation format; the summary template guides conversation summaries.
6. The backend posts the assembled text to LM Studio on port 1234. Qwen2.5 1.5B Instruct generates the answer. Qwen receives neither a MySQL connection nor Nomic vectors.
7. The backend streams text to React. React renders Markdown code fences as copyable language-labelled panels.
8. The completed answer goes through the same JSON/MySQL persistence and indexing path. Summary/hybrid modes refresh bounded source excerpts after saved messages.

See [numbered HLD](hld-flowchart.svg). The separate offline evaluation lane is part of the architecture, not a stage executed after every real chat.

## Responsibilities

| Component | Current responsibility |
|---|---|
| JSON working memory | Conversation records and common filled session blueprint |
| MySQL, local port 3307 | Synchronized conversations, messages, sessions, summaries, image records and vector metadata |
| Nomic through LM Studio | Generates document and query vectors, currently 768 dimensions |
| Chroma | Persistent vector index with text, source IDs, role, ownership and timestamps |
| Neo4j, local Bolt port 7687 | Historical user-source nodes, supported learner facts, topic relationships and provenance |
| Response blueprint | Trusted response-format templates and extractive summary policy |
| Qwen through LM Studio | Generates text from the selected instructions and evidence |

## Memory configurations

- Buffer uses recent conversation messages.
- Summary uses recent messages plus bounded excerpts of older messages in the current chat.
- Vector uses recent history plus semantic retrieval from Chroma.
- Graph uses recent history plus Neo4j facts, with a labelled source-keyword fallback when structured facts do not match.
- Hybrid combines the enabled summary, graph and vector paths. It is an additional application configuration, not a fifth required memory approach.

Neo4j synchronization is automatic when enabled. Every saved message invokes graph reconciliation, but only retained user messages become source nodes and supported patterns become learner facts. A mentioned topic is not proof that a learner studies it. Assistant claims do not automatically become learner facts. Failed synchronization is logged and retrieval retries it.

## Privacy and lifecycle

All model endpoints are loopback-only in the configured local mode. The API's learner header provides scoping, not production authentication. Explicit forgetting reconciles active JSON/MySQL, source-linked vectors, graph records, summaries and affected managed images. Backups, exports, original external images and old provider logs are outside that deletion boundary.

One-hour inactivity expiry is still implemented. It is separate from LM Studio model unloading and from the context window. Cross-session retention ends when the configured session expiry removes the sources.

## Images

An explicitly attached image is stored locally and read using local Tesseract OCR. The backend supplies extracted text, not direct image vision, to Qwen. The strict image-lineage isolation proposed during design discussion has not yet been implemented across all history, summary and retrieval paths. Do not present that proposal as an active guarantee.

## Evaluation

The offline runner loads only official LoCoMo source dialogue and supplied captions into isolated stores, builds context with the production context builder, and generates a short answer locally. Withheld reference answers enter the scorer after generation. Category 1 uses the upstream sub-answer F1 procedure, categories 2–4 use upstream normalized/stemmed F1, and category 5 uses its abstention phrase rule.

The fresh comparison and audit are in `benchmark_outputs/panel/20261108_live_budget/`. Its manifest declares the selected subset, input allowance and decoding settings. Historical experiments retain their own source snapshots. This is not a reproduction of the full MemGPT, Mem0 or A-MEM systems.
