"""Forgetting must clear source history, image copies and searchable vectors."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.database.chroma_repository import ChromaChatRepository, ChatNotFoundError
from backend.models.chat import ChatSummary, Message
from backend.models.learner import MemoryRecord
from backend.ocr.local_ocr import OCRResult


def setup(tmp_path):
    repository = ChromaChatRepository(tmp_path / 'db')
    now = [datetime(2030, 1, 1, tzinfo=timezone.utc)]
    repository.session_memory.clock = lambda: now[0]
    chat = ChatSummary(id='chat-A', title='Test', user_id='A', session_id='session-A',
                       created_at=now[0], updated_at=now[0])
    repository.save_chat(chat)
    message = Message(id='message-A', chat_id=chat.id, user_id='A', session_id=chat.session_id,
                      role='user', content='My name is Amitoj.', timestamp=now[0])
    repository.save_message(message)
    return repository, now, chat, message


def test_common_record_holds_text_and_images_and_expiration_removes_all_owned_copies(tmp_path):
    repo, now, chat, message = setup(tmp_path)
    foreign = chat.model_copy(update={'id': 'chat-B', 'user_id': 'B', 'session_id': 'session-B'})
    repo.save_chat(foreign)
    repo.save_message(message.model_copy(update={'id': 'message-B', 'chat_id': 'chat-B', 'user_id': 'B'}))
    collection = repo._client.get_or_create_collection('semantic_messages_expirytest', embedding_function=None)
    for identifier, user, chat_id in [('message-A', 'A', 'chat-A'), ('message-B', 'B', 'chat-B')]:
        collection.upsert(ids=[identifier], documents=['fact'], embeddings=[[1.0, 0.0]],
                          metadatas=[{'user_id': user, 'chat_id': chat_id}])
    repo.save_memory(MemoryRecord(id='derived-A', user_id='A', timestamp=now[0],
                                 memory='A learner fact', importance=5, type='fact', source_message_id=message.id))
    image = tmp_path / 'slide.png'
    image.write_bytes(b'original image')
    record_path, entry = repo.session_memory.add_image(image, OCRResult('Future', [], 1, 'checksum'),
                                                       user_id='A', chat_id=chat.id)
    record = json.loads(record_path.read_text())
    blueprint_path = Path(__file__).resolve().parents[2] / 'memory_blueprint.json'
    blank_before = blueprint_path.read_bytes()
    assert record.keys() == json.loads(blank_before).keys()
    assert len(record['messages']) == 1 and len(record['images']) == 1
    stored_image = record_path.parent / entry['image']['stored_path']
    now[0] += timedelta(minutes=59)
    assert repo.session_memory.expire() == 0
    # Keep the other learner active so it cannot be swept with A.
    repo.save_message(message.model_copy(update={'id': 'message-B2', 'chat_id': 'chat-B', 'user_id': 'B'}))
    now[0] += timedelta(minutes=1)
    assert repo.session_memory.expire() == 1
    assert not record_path.exists() and not stored_image.exists()
    assert image.exists()  # Original user file is not owned by the memory store.
    assert not collection.get(ids=['message-A'])['ids']
    assert collection.get(ids=['message-B'])['ids'] == ['message-B']
    assert not repo.list_memories('A')
    assert not repo.list_user_messages('A')
    with pytest.raises(ChatNotFoundError):
        repo.get_chat(chat.id, 'A')
    assert repo.get_chat('chat-B', 'B').id == 'chat-B'
    assert blueprint_path.read_bytes() == blank_before


def test_new_message_resets_idle_clock_and_restart_respects_expiry(tmp_path):
    repo, now, chat, message = setup(tmp_path)
    now[0] += timedelta(minutes=50)
    repo.save_message(message.model_copy(update={'id': 'later', 'timestamp': now[0]}))
    now[0] += timedelta(minutes=20)
    assert repo.session_memory.expire() == 0
    reopened = ChromaChatRepository(tmp_path / 'db')
    reopened.session_memory.clock = lambda: now[0]
    assert reopened.get_chat(chat.id, 'A').id == chat.id
    now[0] += timedelta(minutes=40)
    assert reopened.session_memory.expire() == 1
    assert not reopened.list_user_messages('A')


def test_image_activity_extends_same_session_and_failed_cleanup_retries(tmp_path, monkeypatch):
    repo, now, chat, _ = setup(tmp_path)
    now[0] += timedelta(minutes=50)
    image = tmp_path / 'slide.png'; image.write_bytes(b'pixels')
    path, _ = repo.session_memory.add_image(image, OCRResult('Text', [], 1, 'checksum'), user_id='A', chat_id=chat.id)
    now[0] += timedelta(minutes=20)
    assert repo.session_memory.expire() == 0
    now[0] += timedelta(hours=1)
    original = repo.forget_session
    monkeypatch.setattr(repo, 'forget_session', lambda record: (_ for _ in ()).throw(RuntimeError('disk error')))
    with pytest.raises(RuntimeError): repo.session_memory.expire()
    assert path.exists()
    monkeypatch.setattr(repo, 'forget_session', original)
    assert repo.session_memory.expire() == 1


def test_standalone_ocr_also_expires_without_a_chat(tmp_path):
    repo = ChromaChatRepository(tmp_path / 'db')
    now = [datetime(2030, 1, 1, tzinfo=timezone.utc)]
    repo.session_memory.clock = lambda: now[0]
    image = tmp_path / 'slide.png'; image.write_bytes(b'pixels')
    path, entry = repo.session_memory.add_image(image, OCRResult('Text', [], 1, 'checksum'))
    now[0] += timedelta(hours=1)
    assert repo.session_memory.expire() == 1
    assert not path.exists()
    assert not (path.parent / entry['image']['stored_path']).exists()


def test_backend_startup_forgets_sessions_that_expired_while_closed(tmp_path):
    from fastapi.testclient import TestClient
    from backend.config import Settings
    from backend.main import create_app
    repo, now, chat, message = setup(tmp_path)
    # Persist an already-expired timestamp; no one-hour wall-clock sleep needed.
    now[0] = datetime(2000, 1, 1, tzinfo=timezone.utc)
    repo.save_message(message)
    app = create_app(Settings(_env_file=None, chroma_path=tmp_path / 'db'))
    with TestClient(app) as client:
        response = client.get('/chat/chat-A', headers={'X-User-Id': 'A'})
        assert response.status_code == 404
        assert client.get('/chat/list', headers={'X-User-Id': 'A'}).json() == []
