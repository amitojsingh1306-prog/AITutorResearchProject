# Project structure guide

This project has many files because it is split into small, clear parts. The
main idea is:

```text
frontend/  -> what the user sees in the browser
backend/   -> the API and chat logic
chroma_db/ -> local saved chat data
uploads/   -> future uploaded learning files
docs/      -> explanation of how the project is organized
scripts/   -> setup helpers for macOS and Windows
```

If your editor shows hundreds of files under `.venv`, `.venv 2`,
`.venv-mac`, or `frontend/node_modules`, those are installed dependency files,
not the main project code. See
[`docs/what-are-venv-files.md`](what-are-venv-files.md) for that explanation.

## The simple mental model

```text
User types in React UI
        |
        v
frontend/src/api/chatApi.ts sends HTTP request
        |
        v
backend/api/chat.py receives request
        |
        v
backend/services/chat_service.py decides what should happen
        |
        v
backend/database/chroma_repository.py saves or loads chat data
        |
        v
FastAPI returns JSON back to React
```

The frontend should not know how data is stored. The database layer should not
know how buttons look. Each layer has one job.

## Root files

These files sit at the top of the project.

| File or folder | Why it exists |
| --- | --- |
| `README.md` | Main project overview and run commands. Start here. |
| `env.example` | Example frontend API setting. Copy the idea when creating local `.env` files. |
| `SETUP_ENVIRONMENTS.md` | Explains why macOS and Windows need separate Python environments. |
| `.gitignore` | Prevents generated files, secrets, virtual environments, and local data from being committed. |
| `ChatBotTutorAI-portable.zip` | A portable copy/archive of the project. Not part of the running app. |

## Frontend

The frontend is the React app you open at `http://127.0.0.1:5174/`.

```text
frontend/
  package.json
  vite.config.ts
  index.html
  src/
    main.tsx
    App.tsx
    api/
    components/
    types/
    index.css
```

| Area | Why it exists |
| --- | --- |
| `frontend/package.json` | Lists frontend packages and commands such as `npm run dev`. |
| `frontend/vite.config.ts` | Configures Vite, the local development server. |
| `frontend/.env` | Tells the browser app where the backend API is. For this machine it points to `http://127.0.0.1:8000`. |
| `frontend/src/main.tsx` | Starts React and mounts the app into the page. |
| `frontend/src/App.tsx` | Main frontend brain: loads chats, opens chats, creates chats, sends messages, and tracks errors/loading. |
| `frontend/src/api/chatApi.ts` | One place for all frontend-to-backend API calls. |
| `frontend/src/types/chat.ts` | TypeScript shapes that match backend chat responses. |
| `frontend/src/index.css` | Tailwind setup and global visual styles. |

### Frontend components

Components are smaller UI pieces used by `App.tsx`.

| File | Job |
| --- | --- |
| `ChatSidebar.tsx` | Left sidebar, previous chats, new chat button, benchmark/memory labels. |
| `ChatWindow.tsx` | Main chat area, empty state, message list, and composer placement. |
| `MessageComposer.tsx` | Text box and send button. |
| `MessageBubble.tsx` | Displays one user or assistant message. |
| `LoadingBubble.tsx` | Shows the assistant loading animation. |
| `Icons.tsx` | Local reusable icons so the UI does not need another icon package. |

## Backend

The backend is the FastAPI app running at `http://127.0.0.1:8000`.

```text
backend/
  main.py
  config.py
  api/
  services/
  database/
  models/
  llm/
  memory/
  rag/
  utils/
  tests/
```

| Area | Why it exists |
| --- | --- |
| `backend/main.py` | Creates the FastAPI app, enables CORS, connects routes, and prepares services at startup. |
| `backend/config.py` | Keeps settings in one place: app name, ChromaDB path, allowed frontend URLs, model settings. |
| `backend/requirements.txt` | Python packages needed to run the backend. |
| `backend/requirements-dev.txt` | Backend packages plus testing tools. |

### Backend layers

| Folder | Job |
| --- | --- |
| `backend/api/` | HTTP routes. It understands URLs like `/chat/list`, but does not own business logic. |
| `backend/services/` | App behavior. It decides how to create chats, save messages, choose titles, and call an AI client. |
| `backend/database/` | ChromaDB storage. It hides database details from the rest of the app. |
| `backend/models/` | Pydantic schemas. These define the shape of API requests and responses. |
| `backend/utils/` | Small shared helpers, currently time handling. |
| `backend/tests/` | Automated backend checks. |

### AI and research folders

| Folder or file | Why it exists |
| --- | --- |
| `backend/llm/groq_client.py` | Optional Groq API client for real assistant replies. |
| `backend/llm/gemini_client.py` | Optional Gemini API client. It is present as an alternative client. |
| `backend/memory/` | Reserved home for future hybrid memory layers. |
| `backend/rag/` | Reserved home for future retrieval and document search. |

The empty-looking `__init__.py` files are intentional. They tell Python that a
folder is importable as a package.

## Local data folders

| Folder | Why it exists |
| --- | --- |
| `chroma_db/` | Local database files for saved chats. Generated contents are ignored by Git. |
| `uploads/` | Future place for uploaded PDFs, notes, or learning resources. |

The `.gitkeep` files inside these folders are only placeholders. They let Git
keep the folder structure even when the real runtime files are ignored.

## Setup scripts

| File | Why it exists |
| --- | --- |
| `scripts/setup-mac.sh` | Creates `.venv-mac` and installs backend dependencies on macOS. |
| `scripts/setup-windows.ps1` | Creates `.venv-windows` from PowerShell. |
| `scripts/setup-windows.bat` | Creates `.venv-windows` from Command Prompt. |

Python environments are operating-system-specific, so a Windows `.venv` will not
work correctly on macOS. That is why the project uses separate setup scripts.

## Why the project is split this way

| Reason | What it gives us |
| --- | --- |
| Separate frontend and backend | The UI can change without rewriting the API. |
| API layer separate from service layer | Routes stay small and easy to understand. |
| Service layer separate from database layer | Storage can change later without rewriting chat behavior. |
| Typed models | Frontend and backend agree on the shape of chat data. |
| Reserved `memory/` and `rag/` folders | Future research features already have a clean home. |
| Setup scripts | The project can run on both macOS and Windows without sharing broken virtual environments. |

## Files you will edit most often

If you are learning the code, focus here first:

| Goal | Start with |
| --- | --- |
| Change the UI layout | `frontend/src/components/ChatWindow.tsx` or `ChatSidebar.tsx` |
| Change send-message behavior | `frontend/src/App.tsx` and `backend/services/chat_service.py` |
| Add a new backend endpoint | `backend/api/chat.py` |
| Change stored chat data | `backend/database/chroma_repository.py` and `backend/models/chat.py` |
| Change the AI response provider | `backend/services/chat_service.py` and `backend/llm/` |
| Change local ports or API URL | `frontend/.env`, `frontend/vite.config.ts`, and `backend/config.py` |

## What to read in order

1. `README.md`
2. `docs/project-structure.md`
3. `frontend/src/App.tsx`
4. `frontend/src/api/chatApi.ts`
5. `backend/api/chat.py`
6. `backend/services/chat_service.py`
7. `backend/database/chroma_repository.py`

That path follows one complete chat request from browser to backend storage.
