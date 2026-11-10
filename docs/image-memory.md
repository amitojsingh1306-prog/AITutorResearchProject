# Image memory

Every successful OCR command now saves an image copy and a JSON record automatically.
The shared format is shown in `image_memory_blueprint.json`.

```sh
cd /Users/amitoj/Developer/AITutor
.venv/bin/python scripts/ocr_image.py "/path/to/your/image.png"
```

Records are saved to `image_memory/<record_id>.json`; image bytes are copied to
`image_memory/images/<record_id>.<extension>`. The JSON references the copied image
using a path relative to the memory folder and includes its SHA-256 checksum.
Moving or deleting the original screenshot does not remove the saved copy.

The same record holds extracted text, word positions and OCR confidence, elapsed
time, model checksum, user/chat identifiers, and an optional Qwen question/answer.
Use `--question "Explain this slide"` to ask local Qwen about the OCR text.
Use `--user-id` and `--chat-id` to associate the record with a specific conversation.
The default user is `local-user`; no chat association is inferred automatically.
`--output` exports an additional copy of the record. Its image path still refers
to the memory folder, not the export location.

This adds local image persistence, not automatic chatbot retrieval or Chroma
indexing. `indexed_in_chroma` remains false. Qwen receives extracted text only,
not image pixels. OCR content is evidence, not a verified personal fact. Removing
this evidence later requires deleting both the JSON record and its stored image.
The folder is excluded from Git because it may contain private image content.
