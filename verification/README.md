# Verification

Small demonstrations that call the project's actual functions. The verification files are entry points for showing the code; the implementation remains in `backend/`. They do not replace the frontend or constitute a model-accuracy benchmark.

Run from `/Users/amitoj/Developer/AITutor` with its `.venv/bin/python`. Local Nomic and Qwen must be available in LM Studio for the model checks. No cloud model API is used. Database checks require the local project MySQL/Neo4j services and credentials already configured by the project; never display credential files to a panel.

| Command | Actual code exercised | What to show |
|---|---|---|
| `.venv/bin/python verification/verify_nomic_embeds.py` | `SemanticChatMemory.embed()` | Document/query prefixes, local endpoint, unique log marker, actual vector dimensions and coordinates |
| `.venv/bin/python verification/verify_chroma_storage.py` | `save_message()` → `sync()` → `embed()` → Chroma `upsert()` | The same message ID linked to text, vector and metadata |
| `.venv/bin/python verification/verify_cosine.py` | Actual Nomic vectors and Chroma cosine query; actual `retrieve()` | Dot product, both norms, independent cosine, returned distance, and `1 - distance` |
| `.venv/bin/python verification/verify_context.py` | `ChatService._prepare_context()` | Candidates, cutoff, duplicate/history flags, selected system prompt and messages |
| `.venv/bin/python verification/verify_rolling_summary.py` | `RollingSummary.context()` | Bounded older excerpts, recent message IDs, persisted temporary session record |
| `.venv/bin/python verification/verify_blueprint.py` | `load_blueprint()` → `select_template()` → `_prepare_context()` | Which instruction was selected and its presence in the actual prompt |
| `.venv/bin/python verification/verify_qwen.py` | `GroqClient.generate_text()` | Actual local `/chat/completions` request and Qwen reply; class name is historical |
| `.venv/bin/python verification/verify_mysql.py` | Actual repository/SQL mirror and FastAPI patch/delete | Saved, corrected and deleted SQL record |
| `.venv/bin/python verification/verify_neo4j.py` | Existing `scripts/verify_graph_updates.py` | Automatic source/fact synchronization, correction, forgetting and namespace cleanup; requires both Neo4j and MySQL |
| `.venv/bin/python verification/inspect_live_chat.py --follow` | Existing read-only live-chat trace inspector | Actual frontend answers, retrieved source IDs/text and inclusion decisions; default learner is `local-user`; use `--user ID --chat ID` if different |
| `.venv/bin/python verification/verify_evaluation.py` | Existing independent benchmark auditor | Rescore latest completed audited run; no new generations. Can accept a run directory argument |

## OCR and blueprint

Run `.venv/bin/python verification/verify_ocr_blueprint.py` to call the real local Tesseract engine, save a temporary managed image/session record, attach its OCR excerpt and verify selection of the image_explanation template. It prints the actual text prepared for Qwen but does not generate an answer or test full visual understanding.

## Run the component checks together

```bash
.venv/bin/python -B verification/run_all.py --include-databases
```

Without `--include-databases`, MySQL and Neo4j checks are skipped. Checks run sequentially, show failures, and return a nonzero exit code if any component check fails.

## Explain the results accurately

- The storage/search/context demos use temporary files and collections. They do not read or alter your saved conversations.
- The database checks create and clean up isolated namespaces; they can update their verification report files.
- The Nomic check calls the real `embed()` method directly with its required connection settings; no persistent database is needed for that HTTP-only check.
- Cosine is independently recomputed with real query/stored vectors and compared with Chroma within floating-point tolerance. Similarity is not a confidence probability.
- Candidate scores are ordered by distance within each role; the actual application reserves user/assistant candidate slots. The displayed global cosine ranking is not an extra production confidence algorithm.
- `included_in_prompt: false` with `included_as_history: true` means the text was already supplied through recent history. Do not claim that this answer proves older-message semantic retrieval.
- Rolling summary currently selects source excerpts; it is not a generative Qwen summary engine.
- Seeing a template inside a prompt proves insertion, not that every model answer follows it or is correct.
- Component checks show individual paths. Use the live-chat inspector or `scripts/validate_current_tutor.py` for the real streaming chat route. The previously observed non-streaming 60-second timeout is a separate known limitation.
- LoCoMo answer scores are separate from these checks. `scripts/show_evaluation_results.py --answers` displays the saved benchmark results.

## Presentation order

1. Run the relevant check and point to its real output.
2. Open the production function named by the check.
3. Explain its input, operation and returned value.
4. Match the unique request marker in LM Studio's Developer Logs when a model request is involved.
5. State what the check does and does not establish.

The earlier `scripts/verify_lmstudio_connection.py` remains available so existing commands continue working.
