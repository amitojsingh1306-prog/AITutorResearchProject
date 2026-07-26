# File reference

Every project file created for Phase 1 is described below.

## Root

- `.gitignore` — excludes Python caches, virtual environments, frontend build
  output, local environment files, and runtime ChromaDB/upload data.
- `README.md` — project scope, setup commands, API contract, architecture, and
  Phase 1 boundaries.
- `docs/benchmarks-and-memory.md` — benchmark map and hybrid-memory roadmap
  taken from the research notes.
- `chroma_db/.gitkeep` — retains the local database directory in Git while its
  generated contents remain ignored.
- `uploads/.gitkeep` — retains the future resource-upload directory.

## Backend

- `backend/__init__.py` — marks the backend as an importable Python package.
- `backend/main.py` — defines the FastAPI application factory, lifespan-based
  dependency wiring, CORS, router registration, health route, and server entry
  object.
- `backend/config.py` — typed environment configuration and default project
  paths.
- `backend/requirements.txt` — pinned production Python dependencies.
- `backend/requirements-dev.txt` — production dependencies plus test tools.
- `backend/.env.example` — documented backend configuration overrides.

### API

- `backend/api/__init__.py` — marks the API layer as a package.
- `backend/api/dependencies.py` — resolves the application-scoped chat service
  for FastAPI routes.
- `backend/api/chat.py` — implements the four requested REST endpoints using a
  router and typed response models.

### Models

- `backend/models/__init__.py` — marks the model layer as a package.
- `backend/models/chat.py` — Pydantic request, chat, message, detail, and
  response schemas with input constraints.

### Database

- `backend/database/__init__.py` — marks persistence adapters as a package.
- `backend/database/chroma_repository.py` — owns ChromaDB client creation,
  collection schemas, serialization, queries, and timestamp ordering.

### Services

- `backend/services/__init__.py` — marks business services as a package.
- `backend/services/chat_service.py` — orchestrates chat lifecycle, IDs,
  timestamps, derived titles, persistence, and the temporary assistant reply.

### Utilities and future packages

- `backend/utils/__init__.py` — marks shared utilities as a package.
- `backend/utils/time.py` — provides timezone-aware UTC creation and parsing.
- `backend/memory/__init__.py` — reserves the hybrid-memory package boundary.
- `backend/rag/__init__.py` — reserves the retrieval pipeline boundary.
- `backend/llm/__init__.py` — reserves the Ollama integration boundary.

### Tests

- `backend/tests/__init__.py` — marks the backend test suite as a package.
- `backend/tests/test_chat_api.py` — verifies health, missing-chat handling,
  create/send/restore/list behaviour, and real isolated ChromaDB persistence.

## Frontend configuration

- `frontend/package.json` — React/Vite/Tailwind dependencies and development,
  lint, build, and preview commands.
- `frontend/package-lock.json` — reproducible npm dependency graph generated
  from the verified Phase 1 toolchain.
- `frontend/index.html` — minimal Vite host document and page metadata.
- `frontend/vite.config.ts` — React plugin and fixed local development port.
- `frontend/tsconfig.json` — references browser and tooling TypeScript projects.
- `frontend/tsconfig.app.json` — strict browser/React compiler configuration.
- `frontend/tsconfig.node.json` — strict Vite configuration compilation.
- `frontend/tailwind.config.js` — source scanning, dark palette, accent colours,
  and glow token.
- `frontend/postcss.config.js` — Tailwind and Autoprefixer processing.
- `frontend/eslint.config.js` — TypeScript, React Hooks, and refresh lint rules.
- `frontend/.env.example` — documents the optional API base URL.

## Frontend source

- `frontend/src/vite-env.d.ts` — adds Vite environment types.
- `frontend/src/main.tsx` — mounts the React application in strict mode.
- `frontend/src/index.css` — Tailwind layers and global dark-theme/scrollbar
  styling.
- `frontend/src/App.tsx` — owns chat list, active conversation, loading, error,
  creation, restoration, and send state.
- `frontend/src/types/chat.ts` — shared TypeScript types matching API responses.
- `frontend/src/api/chatApi.ts` — typed HTTP client and centralized error
  handling.
- `frontend/src/components/Icons.tsx` — accessible reusable inline SVG icons
  without an extra runtime dependency.
- `frontend/src/components/ChatSidebar.tsx` — responsive navigation, new-chat
  action, conversation history, and mobile overlay.
- `frontend/src/components/ChatWindow.tsx` — header, empty state, restored
  messages, automatic scrolling, and composer layout.
- `frontend/src/components/MessageBubble.tsx` — distinct user/assistant message
  presentation and timestamps.
- `frontend/src/components/LoadingBubble.tsx` — accessible animated assistant
  activity state.
- `frontend/src/components/MessageComposer.tsx` — auto-growing input,
  Enter-to-send behaviour, and send button.
