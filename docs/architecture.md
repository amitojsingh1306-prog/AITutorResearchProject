# Phase 1 architecture

## Request flow

```text
React UI
   │ HTTP/JSON
   ▼
FastAPI router
   │ typed Pydantic models
   ▼
ChatService
   │ business rules and orchestration
   ▼
ChromaChatRepository
   │
   ├── chats collection
   └── messages collection
```

The router contains only HTTP concerns. `ChatService` owns chat behaviour, such
as generating IDs, assigning timestamps, deriving a first-message title, and
creating the Phase 1 placeholder response. `ChromaChatRepository` alone knows
how records are represented in ChromaDB.

## ChromaDB records

### `chats`

- Record ID: chat UUID
- Document: chat title
- Metadata: `chat_id`, `title`, `session_id`, `created_at`, `updated_at`

### `messages`

- Record ID: message UUID
- Document: message content
- Metadata: `chat_id`, `message_id`, `role`, `timestamp`, `session_id`

All timestamps are timezone-aware UTC ISO-8601 strings. Messages are explicitly
sorted after retrieval because collection retrieval order is not a conversation
ordering contract.

Both collections disable ChromaDB's automatic embedding function. Phase 1 adds
a fixed one-dimensional placeholder vector to each record and never performs
similarity search. A later embedding migration can therefore be designed and
benchmarked explicitly rather than silently depending on Chroma's default model.

## Future extension boundaries

Later phases should add components behind interfaces and inject them into
`ChatService`:

- `backend/llm/`: Ollama client and model lifecycle
- `backend/memory/`: buffer, rolling summary, vector summary, graph memory,
  working/short-term, episodic, semantic, and long-term stores
- `backend/rag/`: ingestion, chunking, embedding, indexing, and retrieval
- `backend/services/`: tutor policy, student profile, benchmark, and evaluation
- `backend/api/`: new routers for resources, profiles, experiments, and metrics
- `frontend/src/`: learning workspace and evaluation dashboard screens

Phase 1 does not create placeholder algorithms in these modules. Their package
boundaries are present so later implementations have an intentional home.

## Benchmark targets

| Aspect | Benchmark |
| --- | --- |
| Long-term memory | LoCoMo |
| Memory retention | LongMemEval |
| Retrieval performance | RAGBench |
| General chatbot ability | MT-Bench |
| Educational knowledge | MMLU |

## Hybrid memory roadmap

| Layer | Role |
| --- | --- |
| Buffer | Preserve raw recent chat for immediate conversational context. |
| Rolling summary | Compress older chat history into stable memory summaries. |
| Vector summary | Retrieve semantically relevant past chats and learning notes. |
| Graph memory | Store structured relationships between learner, topics, goals, and misconceptions. |

## Testing strategy

The FastAPI application is created by `create_app(settings)`. Tests provide a
temporary ChromaDB path, so they exercise real persistence without touching the
developer's local conversation data.
