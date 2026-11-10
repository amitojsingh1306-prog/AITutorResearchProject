# Project location

The active project is `/Users/amitoj/Developer/AITutor`.
The Desktop `ChatBotTutorAI` folder contains an `AITutor` link to that same directory.
Use that link or the Developer path: changes affect the same files.

Start LM Studio with Qwen and Nomic loaded, then run:

```sh
cd /Users/amitoj/Developer/AITutor
.venv/bin/python scripts/start_local.py
```

The frontend is at http://127.0.0.1:5173 and the backend at http://127.0.0.1:8000.

The consolidation kept the Developer checkout's newer live-chat implementation
and existing conversation database. Unique OCR files, evaluation tools and
presentation deliverables were copied in with SHA-256 verification.
Conflicting versions and older experimental launchers were archived rather
than replacing the active implementation.

Source backup: `/Users/amitoj/Developer/AITutor-consolidation-backup-20261107`.
The original Desktop directory, including its nested checkout and databases,
is retained at `/Users/amitoj/Desktop/ChatBotTutorAI_ARCHIVE_20261107`.
Older database files are preserved there, not combined with the active database.

Consolidation does not automatically activate older rolling-summary or graph
experiments, or establish a MySQL/Neo4j connection. Those require separate
integration work. OCR remains a separate command and does not modify chat.
