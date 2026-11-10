# Graph memory and rolling summaries

The live backend supports `buffer`, `summary`, `vector`, `graph`, and `hybrid`
through `CHATBOT_MEMORY_CONFIGURATION`. The first four select one memory strategy
plus the same bounded recent-message buffer; hybrid combines them. This is
configuration support, not a completed four-way LoCoMo evaluation.

## Graph

Neo4j Community 2026.10.1 runs locally on Bolt 7687 and HTTP 7474. The server
lives under `.local/`, not in another project checkout. It uses the existing
Java 21 installation. Credentials are generated locally in
`.local/graph_credentials.json` with restricted permissions and excluded from
Git. Usage reporting, fleet monitoring and fleet discovery are disabled.

The graph records:

```
Learner → HAS_FACT → Fact → SUPPORTED_BY → SourceMessage
Learner → HAS_SESSION → Session → HAS_MESSAGE → SourceMessage
Fact → ABOUT → Topic
```

Extraction is rule-based: supported explicit user statements about name,
university, preferences, goals, study topic, difficulty and completion. Assistant
answers, questions and OCR image text do not become learner facts. This is a
limited initial extractor, not unrestricted language understanding. Topic
recognition uses the documented aliases in `TOPICS` in `graph_memory.py`.
Latest assertions replace active values in each supported slot; completion
suppresses an earlier difficulty for the same topic. Every fact retains a source.

For a question about a difficulty in the current algorithm, retrieval follows
the current study fact to its topic and finds difficulty facts linked to that
same topic. This is an actual relationship join, not cosine ranking. The prompt
includes the relevant facts and original user-message excerpts. The trace shows
the relationship path, source IDs and whether evidence fitted the prompt budget.
Qwen can still ignore evidence or answer incorrectly; storage success alone
does not establish answer accuracy.

Graph projections are namespaced by source-database path and user. Source edits
and deletions reconcile before retrieval; one-hour session expiration deletes
the graph's session/messages/facts and orphaned nodes. Only active source JSON
is indexed. Projection rebuilds run in a Neo4j transaction. This small-prototype
rebuild approach is intentionally simple and may be expensive at larger scale.

If Neo4j is unavailable, graph-only mode fails clearly; hybrid records graph as
unavailable while allowing other configured memory to respond. Graph startup
must pass connectivity checks before it is enabled in the app.

Start/status/stop this project's server:

```sh
.venv/bin/python scripts/graph_server.py start
.venv/bin/python scripts/graph_server.py status
.venv/bin/python scripts/graph_server.py stop
```

The combined local launcher starts Neo4j when graph memory is enabled.
The graph remains a separate local service when the frontend/backend stop.

Inspection (use the same user ID as your tutor):

```sh
curl -H 'X-User-Id: local-user' http://127.0.0.1:8000/memory/graph
curl -H 'X-User-Id: local-user' http://127.0.0.1:8000/memory/session/CHAT_ID
.venv/bin/python scripts/verify_graph_memory.py
```

The verification uses temporary source storage and an isolated graph namespace,
then deletes that namespace. Its report is an integration check, not benchmark
accuracy or evidence of general multi-hop reasoning performance.

## Rolling summary

`rolling_summary` and `rolling_summary_meta` in the common blueprint are filled
automatically when earlier history exceeds the configured recent-message limit
(currently ten messages). Up to 600 UTF-8 bytes of older learner excerpts are
kept, with source IDs; recent messages stay in full subject to the prompt budget.
It updates when older source content changes and does not reset the idle timer.

This is an **extractive rolling-summary baseline**. It does not ask Qwen to
invent a paraphrase and does not guarantee retention of every old detail. Blank
learner fields in the blueprint are not automatically populated by this feature.
The summary is included in summary/hybrid mode only, appears in memory traces,
and is removed with its session. Independent source history is retained until
the existing one-hour expiration policy applies.

## References

- https://neo4j.com/docs/operations-manual/current/installation/osx/
- https://neo4j.com/docs/operations-manual/current/configuration/configuration-settings/
- https://neo4j.com/docs/python-manual/current/query-simple/

Archive SHA-256: `afcf4986d47d13dd908427d301d5a9278b2ec7d615a12bb40e22087c7e133e78`.
