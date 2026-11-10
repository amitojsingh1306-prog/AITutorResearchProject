# Local MySQL storage

The tutor uses its own MySQL 9.6 instance on `127.0.0.1:3307`, using the existing
`/usr/local/mysql` binaries. It does not modify the system instance's databases
or credentials. Data/configuration live under `.local/mysql/`. Generated root
and restricted application credentials are in private, Git-ignored files under
`.local/`. The application account can access only `aitutor_memory`.

When `CHATBOT_MYSQL_ENABLED=true`, JSON is the backend's working memory and
MySQL persists the same conversations, sessions, summaries and profiles.
Qwen never connects to MySQL: ChatService reads the working JSON and sends a
bounded text prompt through LM Studio. Chroma stores actual
dense vectors. Neo4j stores explicit relationships. MySQL is not a fourth copy
of the vector values or a replacement graph engine.

| Table | Content |
|---|---|
| conversations | Chat ownership, title, session ID and full typed record |
| messages | User/assistant messages, attachment references and memory trace |
| learner_profiles | Account/profile records; this does not infer profile facts |
| memory_sessions | Common filled blueprint and idle expiry |
| conversation_summaries | Extractive summary and its source metadata |
| image_records | Image reference/checksum, OCR details and question/answer |
| vector_memory_metadata | Actual collection, model, measured dimension, hash and sync time |
| storage_scopes | One-time migration marker for each source storage directory |

Tables use source-directory namespaces for isolated experiments, parameterized
queries, transactions and ownership-preserving foreign keys. Source document
updates use transactional upserts and removal reconciliation. This compatible
adapter currently reads scoped document sets rather than optimizing every
query into per-user SQL; it is a prototype, not a scale-performance claim.

Initial startup imports existing JSON once and retains a local pre-migration
backup. Later startup preserves existing JSON; missing complete files can be
restored from MySQL. Writes first persist a private pending-operation snapshot,
then atomically replace JSON and commit its MySQL mirror. On failure, a read or
the next startup retries pending operations before serving context. Operations
use the session file lock to coordinate local processes. These snapshots contain
private working data and are removed after synchronization. Do not edit JSON or
SQL manually while the tutor is running. Account profiles are separate from
session retention.

The one-hour idle cleanup removes a session's SQL messages/conversation,
blueprint, summary, image metadata and vector metadata, together with its known
Chroma, Neo4j and owned image records. A different learner's records remain.
Original screenshots, exports and backups are not deleted. MySQL, files,
Chroma and Neo4j are not one distributed transaction: cleanup is idempotent and
the session manifest is retained if a step fails, so cleanup can retry.
If MySQL synchronization fails, the request fails rather than claiming success;
the pending operation is retained for retry. This is recoverable coordination,
not an atomic transaction across MySQL, JSON, Chroma and Neo4j.

`response_blueprint.json` holds an array of response templates and the extractive
rolling-summary policy. Templates guide normal explanations, conversation summaries
and explicitly attached image questions; they are not guaranteed model compliance.
Summary/hybrid modes refresh their bounded source-derived summary after every
saved message. This is not a new generative summarization model. The full image
lineage isolation design discussed separately is not implemented by these templates.

MySQL Workbench can open `docs/workbench_memory.sql` to inspect conversation,
session, response-template and summary mappings. Use FastAPI update/delete/forget
operations so all stores are reconciled rather than deleting SQL rows directly.

```sh
.venv/bin/python scripts/mysql_server.py status
.venv/bin/python scripts/mysql_server.py start
.venv/bin/python scripts/mysql_server.py stop
curl -H 'X-User-Id: local-user' http://127.0.0.1:8000/memory/storage
.venv/bin/python scripts/verify_mysql_storage.py
```

The normal local launcher starts/checks this MySQL instance when enabled.
Verification uses temporary source storage and namespaces, then removes its
own MySQL and Neo4j test records. The report is an integration check, not a
LoCoMo evaluation score.

Official connector reference:
https://dev.mysql.com/doc/connector-python/en/connector-python-connection-pooling.html
