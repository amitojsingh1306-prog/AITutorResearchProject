# Low-level design

The active generation path is ChatService's direct context builder and local model client. Legacy multi-agent generation methods remain in the repository, but the current streaming route does not call that agent chain.

See [numbered LLD](lld-flowchart.svg).

## Startup wiring

`backend/main.py:create_app()` creates the repository through `database/factory.py`, initializes SemanticChatMemory and optional Neo4jMemory, and injects them into ChatService. The configured GroqClient instance targets LM Studio's local compatible endpoint; the historical class name does not mean a cloud request.

## Request execution

| Step | Caller and function | Data and result |
|---|---|---|
| 1 | `App.tsx:sendMessage()` calls `chatApi.streamMessage()` | Text, learner ID, chat ID and optional selected attachment ID |
| 2 | `backend/api/chat.py:stream_message()` calls `ChatService.stream_message()` | Checks ownership and attachment access, then returns streaming events |
| 3 | `MemoryMutations.control()` | Detects supported update/forget requests before generation |
| 4 | `ChatService._new_message()` then `repository.save_message()` | Creates IDs/timestamp and saves the user record |
| 5 | `SemanticChatMemory.sync()` calls `embed()` then Chroma `upsert()` | New/changed text goes to local Nomic with `search_document:`; removed IDs leave the index |
| 6 | `Neo4jMemory.sync()` | Reconciles user-source messages and supported facts under learner/project scope |
| 7 | `_direct_stream_reply()` calls `_prepare_context()` | Reads current history, optional RollingSummary, graph facts and vector candidates |
| 8 | `select_template()` and context selection | Adds response and code-format instructions, filters similarity, removes duplicates, enforces byte-based allowance |
| 9 | `_llm_client.stream_reply()` calls `_chat_stream()` | Posts system/text messages to local `/v1/chat/completions` |
| 10 | `_sse('chunk', ...)` then React `onChunk()` | Displays streamed response; MarkdownContent handles code panels |
| 11 | `repository.save_message(assistant_message)` | Saves completed text and trace, refreshes derived summary and reconciles indexes |
| 12 | `_sse('done', ...)` then React `onDone()` | Final persisted message replaces the streaming placeholder |

## Source persistence

`MySQLChatRepository._write_json_file()` journals a private pending snapshot, atomically replaces JSON and commits the MySQL mirror. `_read_json_file()` replays pending writes before reading JSON. Missing complete working files can recover from SQL; an empty JSON map is not treated as a missing file. `persist_session_record()` mirrors the filled session blueprint and summaries.

Session IDs map conversations to their saved records. The current session-file key derives from learner ID plus chat ID; it does not represent unlimited separately keyed session IDs inside one chat.

## Summary and blueprint

`response_blueprint.json` contains an array of normal-content, conversation-summary and image-explanation templates. `response_blueprint.py:select_template()` selects one; `_prepare_context()` sends its instruction to Qwen as part of the system prompt. This does not guarantee exact compliance or correct calculations.

`RollingSummary.refresh()` runs after saved messages in summary/hybrid modes. `context()` retains recent messages and selects bounded older excerpts, preferring learner statements. Source hashes invalidate outdated summaries, and source IDs make the excerpt selection inspectable. Session persistence synchronizes the summary to MySQL.

## Vector search and selection

`SemanticChatMemory.retrieve()` reconciles retained sources, embeds the current question with `search_query:`, and calls Chroma using `query_embeddings`. The collection uses cosine distance, so the displayed similarity is `1 - distance`. Candidate allocation reserves four user slots and two assistant slots. Context selection applies the configured 0.60 cutoff, avoids duplicate history and fits excerpts into the remaining allowance.

The current live path does not rank by a separate calibrated confidence probability. The input-bound helper uses UTF-8 bytes plus a formatting allowance, not the Qwen tokenizer. Actual token usage is recorded separately during evaluation.

## Graph retrieval

`Neo4jMemory.retrieve()` selects supported fact types/topics and can join the learner's study topic to a related difficulty. Facts retain source-message IDs and timestamps. If none match, it returns explicitly labelled source-keyword matches rather than claiming structured reasoning. Current-chat recap requests scope both vector and graph retrieval to that chat; other learner-memory questions may search retained chats for that learner.

## Corrections, forgetting and race protection

PATCH and DELETE message routes call `MemoryMutations.edit()` and `delete()`. A supported chat command calls `control()` then `forget()` or an update plan. `_apply()` synchronizes source changes and clears affected vectors, graph evidence, summaries, copied diagnostic context and managed image records. A persisted operation remains pending on failure; the API must not confirm successful cleanup.

The chat service checks a memory revision while streaming and before saving the assistant response. If memory changed, it rejects the stale completion so it cannot restore deleted context. The shared session/file lock coordinates local processes. These operations do not form one transaction across every database and filesystem.

## Offline evaluation

`run_panel_evaluation.py:seed_corpus()` imports source dialogue. For each held-out question and memory configuration, the runner calls the production `_prepare_context()` and sends a fixed short-answer request to local Qwen. It does not save references or generated predictions into test memory.

The downloaded upstream QA scoring functions score only after generation. `audit_panel_results.py` independently rescores predictions and checks question/reference mapping, request hashes, source IDs, corpus immutability and cleanup coverage. The runner saves exact requests, predictions, timings, actual input/output tokens, traces, manifests and source snapshots. It evaluates the context builder directly; HTTP save/forget/image behaviour is checked separately.

One-command report: `.venv/bin/python scripts/show_evaluation_results.py`. Add `--answers` to print every prediction. This viewer selects the latest completed independently audited run and does not regenerate scores or call a model.
