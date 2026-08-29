# ChatbotTutorAI

ChatbotTutorAI is a FastAPI + React educational tutor chatbot with persistent
chat history, real streaming responses, and a separate long-term student memory
layer.

The important design rule is:

```text
chat messages != long-term memory
```

Normal chat transcripts are stored as messages. Durable learner information is
stored separately as structured memories in ChromaDB and used as hidden tutor
context.

## Current Capabilities

- React + Vite frontend with a ChatGPT-style chat experience
- FastAPI backend on `http://localhost:8000`
- Streaming assistant responses over SSE
- Groq as the primary LLM provider
- Ollama Qwen fallback when Groq fails or is unavailable
- ChromaDB persistence for chats, messages, learner profiles, and memories
- Rolling recent-message context instead of appending the full transcript
- Long-term memory with ADD / UPDATE / DELETE / NOOP decisions
- Hidden memory grounding so raw retrieved memories are not shown to the user
- Retrieval routing so Chroma does not replace current chat context
- A-MEM-inspired evolved student memories for learning progress

## Architecture

```text
User message
    |
    v
FastAPI ChatService
    |
    v
TutorOrchestrator
    |
    +--> Intent Agent
    +--> Conversation State Agent
    +--> Memory Agent
    |       |
    |       +--> MemoryManager
    |       |       |
    |       |       +--> Working memory: recent useful chat messages
    |       |       +--> Long-term memory: ChromaDB memories collection
    |       |       +--> Memory decision: ADD / UPDATE / DELETE / NOOP
    |       |       +--> A-MEM evolution: update related memories, avoid duplicates
    |       |
    |       +--> VectorMemoryRetriever
    |
    +--> Knowledge Agent
    +--> Teaching Planner
    +--> Response Generation Agent
    |
    v
Groq primary LLM
    |
    +--> Ollama Qwen fallback
    |
    v
Frontend streaming response
```

## Project Structure

```text
ChatBotTutorAI/
├── backend/
│   ├── api/                  FastAPI routes
│   ├── agents/               Intent, memory, planning, response agents
│   ├── database/             ChromaDB repository
│   ├── llm/                  Groq, Ollama, and fallback clients
│   ├── memory/               Working memory, retrieval, memory manager
│   ├── models/               Pydantic domain/API models
│   ├── orchestration/        Tutor pipeline
│   ├── services/             Chat service
│   └── tests/                Backend tests
├── frontend/                 React, Vite, TypeScript, Tailwind CSS
├── chroma_db/                Local ChromaDB data, ignored by Git
├── uploads/                  Future learning-resource uploads
└── docs/                     Extra architecture notes
```

## LLM Providers

The backend keeps one LLM interface and chooses providers internally.

Default flow:

```text
Try Groq
    |
    +-- success --> return Groq response
    |
    +-- failure/rate limit/timeout --> fallback to Ollama Qwen
```

Relevant environment variables:

```dotenv
GROQ_API_KEY=your_groq_key
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_NUM_PREDICT=700

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b
OLLAMA_KEEP_ALIVE=30m
OLLAMA_NUM_PREDICT=700
```

Do not commit `.env`.

## Memory System

The memory layer is separate from chat messages.

### Working Memory

Working memory is the short rolling context sent to the model for conversation
continuity. It keeps recent useful messages and filters out low-signal turns
like greetings.

### Long-Term Memory

Long-term memory is stored in the ChromaDB `memories` collection. The
MemoryManager decides whether each user turn should become memory:

- `ADD`: new durable learner information
- `UPDATE`: changed or improved learner state
- `DELETE`: user asks to forget something
- `NOOP`: temporary chat, greeting, or non-durable information

Memory categories:

- Goal
- Knowledge State
- Learning Difficulty
- Preference
- Achievement
- Fact

### A-MEM-Inspired Evolved Student Memories

When a durable memory is saved, the backend now stores a structured student
memory object inside the existing `MemoryRecord.memory` field.

Example:

```json
{
  "topic": "Recursion",
  "concepts": ["Recursion", "Base Cases"],
  "difficulty": "Learning difficulty: I am confused about recursion base cases",
  "progress": "Knowledge state: I understood recursion examples but need practice",
  "important_facts": [],
  "tags": ["Knowledge State", "Recursion", "Base Cases"],
  "timestamp": "2026-08-07T..."
}
```

Before creating a new memory, the MemoryManager searches related memories. If a
matching topic/concept exists, it evolves that existing memory instead of adding
a duplicate.

Example:

```text
Turn 1:
I am confused about recursion base cases

Memory:
topic=Recursion
difficulty=confused about recursion base cases

Turn 2:
I understood recursion examples but need practice

Updated same memory:
topic=Recursion
difficulty=confused about recursion base cases
progress=understood recursion examples but need practice
```

## Retrieval Rules

Chroma is only a retrieval memory store. It does not decide what the user
discussed and it does not replace the current chat context.

Retrieval modes:

- `CURRENT_CONVERSATION`: use current chat history only, Chroma disabled
- `USER_PROFILE`: retrieve profile-style memories like facts, goals, preferences
- `KNOWLEDGE`: retrieve knowledge-state memories for teaching personalization
- `GENERAL`: retrieve filtered relevant memories

Retrieved memories are hidden tutor notes by default. The assistant should use
them for personalization, but not quote or list them unless the user explicitly
asks about memory/history.

## Memory Debug Logs

After every chat turn, the backend prints the current user's evolved memories:

```text
[EVOLVED MEMORY DEBUG] user_id=... active_memory_count=...
[EVOLVED MEMORY DEBUG] 1 id=... type=... topic=Recursion concepts=[...] difficulty=... progress=... facts=[...] tags=[...]
```

Use this to verify:

- recursion confusion creates a memory
- later improvement updates the same memory
- duplicate recursion memories are not created

Other useful debug blocks:

```text
[MEMORY ROUTER]
[MEMORY DEBUG]
[RETRIEVAL DEBUG]
[GENERATION DEBUG]
```

## Run the Backend

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

On this Mac workspace, the existing local environment is:

```bash
.venv-mac/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"healthy"}
```

## Run the Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

If the backend is hosted somewhere else, create `frontend/.env`:

```dotenv
VITE_API_URL=http://localhost:8000
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/chat/create` | Create an empty chat |
| `GET` | `/chat/list` | List chats by recent activity |
| `GET` | `/chat/{id}` | Restore one chat and its messages |
| `POST` | `/chat/{id}/message` | Send a non-streaming chat message |
| `POST` | `/chat/{id}/message/stream` | Send a streaming chat message |
| `GET` | `/health` | Check backend health |

## Test

Run backend tests:

```bash
.venv-mac/bin/python -m pytest backend/tests/test_chat_api.py
```

Current verified result:

```text
44 passed
```

## Manual Memory Test

In the chat UI, send:

```text
I am confused about recursion base cases
```

Then send:

```text
I understood recursion examples but need practice
```

Check the backend terminal. You should see one evolved `Recursion` memory, not
two duplicate recursion memories.

