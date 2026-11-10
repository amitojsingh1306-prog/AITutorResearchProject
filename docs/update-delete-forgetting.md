# Update, delete and explicit forgetting

FastAPI now provides ownership-checked operations:

- `PATCH /chat/{chat_id}/messages/{message_id}` with `{"content":"replacement text"}`
- `DELETE /chat/{chat_id}/messages/{message_id}`
- `DELETE /chat/{chat_id}`
- `POST /chat/{chat_id}/forget` with `{"target":"my name"}`

The normal streamed chat also recognizes explicit requests such as:

```
Forget my name.
Forget my university.
Forget my preferences.
Forget about recursion.
Forget the last exchange.
Forget this chat.
Forget all my memories.
Update my name to AJ.
Change my university to S.R.M University.
```

Named personal facts are removed across that user's saved conversations. A
request to forget this chat applies to that chat; forgetting all memories is
explicitly broader. Ambiguous requests such as `forget it` ask for clarification.
Negative instructions such as `don't forget my name` do not trigger deletion.
This is a rule-based command vocabulary, not universal natural-language intent
recognition. An unmatched target is reported, not falsely acknowledged as deleted.

Forget requests are handled by backend code, not by asking Qwen to promise it
forgot. The request is saved in neutral wording so a forgotten value in the
command cannot re-enter memory. Generated confirmations do not repeat it.
Explicit updates persist the replacement assertion before confirming success.

The cleanup changes authoritative MySQL messages and their JSON views, removes
deleted/obsolete vectors and source-linked durable records, reconciles Neo4j,
clears summaries and traces, and removes affected owned image copies/OCR records.
Named fact removal preserves unrelated clauses where recognized. Generated
responses depending on changed source messages may be discarded rather than
left as stale evidence. Chat titles are reset when their content may be stale.
The frontend refreshes the conversation and sidebar after a completed operation.

A small content-free operation journal (IDs and requested replacement text, not
the forgotten text) supports idempotent retry. Cleanup failures are reported as
pending rather than successful; pending work is retried before source access,
at startup and by the background worker. Generation revision checks prevent an
in-flight response from saving a fact after it has been deleted.

Account identifiers/email, original files outside managed storage, old exports,
provider logs and backups are outside active-memory deletion. This is not
forensic secure erasure. Independently paraphrased copies that have neither a
matching literal value nor a recorded source dependency cannot be reliably
identified by this initial rule-based implementation.
