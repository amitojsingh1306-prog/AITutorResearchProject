# Memory Retrieval Evaluation Flow

This file documents the measurable memory layer used for demos and evaluation.

## Live Tutor Memory

```text
React chat UI
→ FastAPI /chat route
→ chat_service.py
→ save user message in chroma_db/messages.json
→ read recent JSON history
→ build prompt/context window
→ call model provider
→ stream assistant response
→ save assistant response in chroma_db/messages.json
```

JSON is the stable live memory source.

## Embedding Sync Layer

```text
chroma_db/messages.json
→ scripts/sync_json_memory_to_chroma.py
→ Chroma collection: json_message_semantic_embeddings
```

The sync script converts saved JSON messages into semantic vector records. The
current semantic model is `sentence-transformers/all-MiniLM-L6-v2`, which
creates dense 384-dimensional embeddings. If the model cannot be loaded, the
code falls back to the older deterministic 64-dimensional vector function so the
app still runs.

## Retrieval Metrics Layer

```text
GET /memory/search?query=recursion&token_budget=350
→ embed query
→ compare query vector with stored memory vectors
→ compute cosine similarity
→ rank candidate memories
→ apply token buffer
→ mark stale memories
→ return retrieval matrix and metrics
```

Returned metrics:

- `retrieval_latency_ms`: time taken to retrieve/rank memories.
- `cosine_similarity`: vector similarity between query and memory.
- `confidence_score`: similarity plus lexical overlap minus stale penalty.
- `precision_at_k_proxy`: fraction of returned memories sharing query terms.
- `memory_token_buffer`: budget, used tokens, and skipped memories.
- `stale`: whether a memory is older than the configured stale threshold.

## Delete Handling

```text
DELETE /memory/debug/{embedding_id}
→ deletes one Chroma embedding record

DELETE /memory/message/{message_id}
→ deletes the JSON message
→ deletes the derived Chroma embedding
```

This lets stale or incorrect memories be removed from the inspection layer and,
when needed, from the JSON source of truth.
