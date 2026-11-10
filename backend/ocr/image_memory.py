"""Persist image evidence and OCR using one local JSON record format."""

from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import shutil
from uuid import uuid4

from backend.ocr.local_ocr import OCRResult

DEFAULT_MEMORY_DIRECTORY = Path(__file__).resolve().parents[2] / 'chroma_db' / 'session_memory'
_stores = {}


def write_record(path: Path, record: dict) -> None:
    """Replace one complete JSON record atomically, never a partially written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{uuid4().hex}.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            os.chmod(temporary, 0o600)
            json.dump(record, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_image_memory(image: Path, result: OCRResult, *,
                      directory: Path = DEFAULT_MEMORY_DIRECTORY,
                      user_id: str = 'local-user', chat_id: str | None = None,
                      question: str | None = None) -> tuple[Path, dict]:
    """Copy the image so recall survives moving/removing the original screenshot.

    The JSON stores a reference and checksum, not image bytes or an embedding.
    OCR text is source evidence; it is not a verified learner fact.
    """
    return _store(directory).add_image(image, result, user_id=user_id,
                                      chat_id=chat_id, question=question)


def _store(directory):
    # Imports stay local because the repository also uses write_record above.
    from backend.database.chroma_repository import ChromaChatRepository
    from backend.memory.session_memory import SessionMemory
    root = Path(directory).expanduser().resolve()
    if root not in _stores:
        from backend.config import Settings
        settings = Settings()
        if root.parent == settings.chroma_path.resolve():
            from backend.database.factory import create_repository
            repository = create_repository(settings)
        else:
            repository = ChromaChatRepository(root.parent)
        repository.session_memory = SessionMemory(repository, root)
        if settings.graph_enabled and root.parent == settings.chroma_path.resolve():
            from backend.memory.graph_memory import Neo4jMemory
            credentials = json.loads(settings.graph_credentials_file.read_text())
            repository.graph_memory = Neo4jMemory(repository, settings.graph_uri,
                credentials['username'], credentials['password'], settings.graph_database)
        _stores[root] = repository.session_memory
    return _stores[root]


def update_image_memory(path: Path, entry: dict):
    _store(Path(path).parent).update_image(path, entry)
