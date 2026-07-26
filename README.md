# ChatbotTutorAI

ChatbotTutorAI is the Phase 1 foundation for an IEEE research project exploring
a **local, hybrid-memory student tutor AI**. This release intentionally provides
only the chat application and persistent conversation storage. Ollama,
sentence-transformers, hybrid memory strategies, RAG, student modelling,
benchmarking, and evaluation are reserved for later phases.

## Phase 1 capabilities

- Responsive, dark ChatGPT-like React interface
- Mobile and desktop sidebar with persisted chat history
- New-chat, chat restoration, message, loading, and error flows
- Modular FastAPI API with typed Pydantic schemas
- Persistent ChromaDB collections for chat metadata and messages
- Required message metadata: `chat_id`, `message_id`, `role`, `timestamp`,
  `session_id`
- Placeholder assistant response: `Backend connected successfully.`
- Isolated API tests and a production frontend build

## Architecture

```text
ChatbotTutorAI/
├── frontend/                 React, Vite, TypeScript, Tailwind CSS
├── backend/
│   ├── api/                  HTTP routers and dependencies
│   ├── services/             Application orchestration
│   ├── database/             ChromaDB persistence adapter
│   ├── models/               Pydantic API/domain schemas
│   ├── memory/               Reserved hybrid-memory boundary
│   ├── rag/                  Reserved retrieval boundary
│   ├── llm/                  Reserved Ollama boundary
│   ├── utils/                Shared helpers
│   ├── tests/                Backend API tests
│   └── main.py               FastAPI application factory and entry point
├── chroma_db/                Local persistent data (ignored by Git)
├── uploads/                  Future learning-resource uploads
├── docs/                     Architecture and file reference
└── README.md
```

The HTTP layer depends on `ChatService`, which depends on a ChromaDB repository.
This separation is deliberate: future memory, retrieval, tutor policy, and LLM
components can be injected into the service without rewriting the API or UI.
See [`docs/project-structure.md`](docs/project-structure.md) for a beginner
friendly map of the folders, [`docs/architecture.md`](docs/architecture.md) for
the extension map, and [`docs/file-reference.md`](docs/file-reference.md) for
every created file.

## Prerequisites

- Python 3.10 or newer
- Node.js 20.19 or newer with npm
- Git

## Run the backend

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements-dev.txt
python -m uvicorn backend.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`; interactive documentation is
at `http://localhost:8000/docs`.

Run backend tests:

```powershell
python -m pytest backend\tests -q
```

## Run the frontend

Open a second PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

Create `frontend/.env` only when the API is hosted somewhere other than the
default:

```dotenv
VITE_API_URL=http://localhost:8000
```

Verify the production build:

```powershell
cd frontend
npm run lint
npm run build
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/chat/create` | Create an empty chat |
| `GET` | `/chat/list` | List chats by most recent activity |
| `GET` | `/chat/{id}` | Restore a chat and its messages |
| `POST` | `/chat/{id}/message` | Store a user message and placeholder reply |
| `GET` | `/health` | Check API availability |

## Storage model

ChromaDB uses two collections:

- `chats`: one record per chat with title, session ID, creation time, and update
  time.
- `messages`: one document per message with the required metadata fields. Query
  results are sorted by their ISO-8601 UTC timestamp before being returned.

Runtime data is local and excluded from Git. The tracked `.gitkeep` file retains
the expected directory in a fresh clone.

## Phase boundary

No semantic embeddings are generated in Phase 1. Records receive a fixed
one-dimensional placeholder vector because ChromaDB requires a vector when its
automatic embedding function is disabled. The application only performs
metadata/document reads, never similarity queries. This avoids loading Chroma's
default ONNX model or prematurely coupling chat history to a future embedding
and memory strategy.
