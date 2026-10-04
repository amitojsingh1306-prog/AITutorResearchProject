"""Sync JSON chat history into a Chroma embedding collection.

The live tutor uses JSON as the source of truth for chat memory. This script
builds a derived Chroma vector index from that JSON history for demos,
inspection, and offline retrieval experiments.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import chromadb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.chroma_repository import ChromaChatRepository  # noqa: E402
from backend.models.chat import Message  # noqa: E402


DEFAULT_CHROMA_PATH = PROJECT_ROOT / "chroma_db"
DEFAULT_MESSAGES_PATH = DEFAULT_CHROMA_PATH / "messages.json"
COLLECTION_NAME = "json_message_embeddings"


def load_messages(path: Path) -> list[Message]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return [
        Message.model_validate_json(document)
        for document in payload.values()
        if isinstance(document, str)
    ]


def should_index(message: Message, *, include_assistant: bool) -> bool:
    if not message.content.strip():
        return False
    if message.role == "assistant" and not include_assistant:
        return False
    return True


def sync_messages(
    *,
    messages_path: Path,
    chroma_path: Path,
    user_id: str | None,
    include_assistant: bool,
    dry_run: bool,
    limit: int | None,
) -> int:
    messages = [
        message
        for message in load_messages(messages_path)
        if should_index(message, include_assistant=include_assistant)
        and (user_id is None or message.user_id == user_id)
    ]
    messages = sorted(messages, key=lambda item: item.timestamp)
    if limit is not None:
        messages = messages[-limit:]

    if dry_run:
        print(f"Would sync {len(messages)} messages into Chroma collection {COLLECTION_NAME!r}.")
        return len(messages)

    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=None,
        metadata={
            "description": "Derived embeddings copied from JSON chat history",
            "source": str(messages_path),
        },
    )

    for message in messages:
        collection.upsert(
            ids=[f"json-message-{message.id}"],
            documents=[message.content],
            embeddings=[ChromaChatRepository.embed_text(message.content)],
            metadatas=[
                {
                    "source": "messages.json",
                    "message_id": message.id,
                    "chat_id": message.chat_id,
                    "user_id": message.user_id,
                    "role": message.role,
                    "timestamp": message.timestamp.isoformat(),
                }
            ],
        )

    print(f"Synced {len(messages)} messages into Chroma collection {COLLECTION_NAME!r}.")
    return len(messages)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a Chroma embedding index from JSON chat history.",
    )
    parser.add_argument("--messages", type=Path, default=DEFAULT_MESSAGES_PATH)
    parser.add_argument("--chroma-path", type=Path, default=DEFAULT_CHROMA_PATH)
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--include-assistant", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    sync_messages(
        messages_path=args.messages,
        chroma_path=args.chroma_path,
        user_id=args.user_id,
        include_assistant=args.include_assistant,
        dry_run=args.dry_run,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
