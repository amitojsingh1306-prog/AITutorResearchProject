"""Common text/image session records, derived summaries and idle forgetting."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
from functools import wraps
import hashlib
import json
import mimetypes
from pathlib import Path
import shutil
from threading import RLock, local
from uuid import uuid4

from backend.ocr.image_memory import write_record

BLUEPRINT = Path(__file__).resolve().parents[2] / 'memory_blueprint.json'


def session_locked(method):
    """Serialize JSON writes with expiration, including across local processes."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.session_memory.transaction():
            mutations=getattr(self,'mutations',None)
            if mutations is not None:mutations.resume()
            return method(self, *args, **kwargs)
    return wrapped


class SessionMemory:
    def __init__(self, repository, directory: Path, *, clock=None):
        self.repository = repository
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        self._local = local()

    @contextmanager
    def transaction(self):
        with self._lock:
            if getattr(self._local, 'depth', 0):
                self._local.depth += 1
                try:
                    yield
                finally:
                    self._local.depth -= 1
            else:
                with (self.directory / '.lock').open('a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    self._local.depth = 1
                    try:
                        yield
                    finally:
                        self._local.depth = 0
                        fcntl.flock(lock, fcntl.LOCK_UN)

    def _path(self, user_id, chat_id):
        key = hashlib.sha256(json.dumps([user_id, chat_id]).encode()).hexdigest()
        return self.directory / f'{key}.json'

    def _load(self, user_id, chat_id, session_id):
        path = self._path(user_id, chat_id)
        if path.exists():
            return path, json.loads(path.read_text())
        record = json.loads(BLUEPRINT.read_text())
        record.update(user_id=user_id, chat_id=chat_id, session_id=session_id,
                      created_at=self.clock().isoformat())
        return path, record

    def _touch(self, record):
        now = self.clock()
        record.update(last_activity_at=now.isoformat(),
                      expires_at=(now + timedelta(seconds=3600)).isoformat())

    def persist(self,path,record):
        mirror=getattr(self.repository,'persist_session_record',None)
        if mirror is not None:
            mirror(Path(path),record)
            return
        sql=getattr(self.repository,'sql_store',None)
        if sql is not None:sql.save_session(Path(path).stem,record)
        write_record(Path(path),record)

    def track_chat(self, chat):
        with self.transaction():
            path, record = self._load(chat.user_id, chat.id, chat.session_id)
            # A title/metadata update must not extend an otherwise idle session.
            if record['last_activity_at'] is None:
                self._touch(record)
                self.persist(path, record)

    def track_message(self, message):
        with self.transaction():
            path, record = self._load(message.user_id, message.chat_id, message.session_id)
            # Include earlier turns when an existing conversation first opts in.
            raw = self.repository._read_json_file(self.repository._message_file)
            record['messages'] = [json.loads(value) for value in raw.values()
                                  if json.loads(value).get('chat_id') == message.chat_id
                                  and json.loads(value).get('user_id') == message.user_id]
            record['messages'].sort(key=lambda item: item['timestamp'])
            self._touch(record)
            self.persist(path, record)

    def add_image(self, image, result, *, user_id='local-user', chat_id=None, question=None):
        with self.transaction():
            self.expire()
            session_id = 'image-session'
            if chat_id:
                chat = self.repository.get_chat(chat_id, user_id)
                session_id = chat.session_id
            path, record = self._load(user_id, chat_id, session_id)
            image_id = uuid4().hex
            images = self.directory / 'images'
            images.mkdir(exist_ok=True, mode=0o700)
            source = Path(image).expanduser().resolve(strict=True)
            stored = images / f'{image_id}{source.suffix.lower()}'
            try:
                shutil.copyfile(source, stored)
                stored.chmod(0o600)
                entry = {
                    'id': image_id,
                    'image': {'original_filename': source.name,
                              'stored_path': str(stored.relative_to(self.directory)),
                              'sha256': hashlib.sha256(stored.read_bytes()).hexdigest(),
                              'media_type': mimetypes.guess_type(source.name)[0],
                              'size_bytes': stored.stat().st_size},
                    'ocr': result.to_dict(),
                    'generation': {'question': question, 'model': None, 'answer': None,
                                   'status': 'pending' if question else 'not_requested', 'error': None},
                    'retrieval': {'indexed_in_chroma': False},
                }
                record['images'].append(entry)
                self._touch(record)
                self.persist(path, record)
            except BaseException:
                stored.unlink(missing_ok=True)
                raise
            return path, entry

    def update_image(self, path, entry):
        with self.transaction():
            self.expire()
            if not Path(path).is_file():
                raise ValueError('Image session expired; its answer was not saved.')
            record = json.loads(Path(path).read_text())
            matches = [item for item in record['images'] if item['id'] == entry['id']]
            if not matches:
                raise ValueError('Image no longer belongs to this session.')
            matches[0].update(entry)
            self.persist(Path(path), record)

    def expire(self):
        """Remove expired owned data; retain the manifest if cleanup fails to retry."""
        deleted = 0
        with self.transaction():
            for path in self.directory.glob('*.json'):
                record = json.loads(path.read_text())
                expiry = datetime.fromisoformat(record['expires_at'])
                if expiry > self.clock():
                    continue
                # Remove searchable copies before removing the session manifest.
                self.repository.forget_session(record)
                for entry in record['images']:
                    target = (self.directory / entry['image']['stored_path']).resolve()
                    image_root = (self.directory / 'images').resolve()
                    if target.parent != image_root:
                        raise ValueError('Refusing image deletion outside session storage.')
                    target.unlink(missing_ok=True)
                sql=getattr(self.repository,'sql_store',None)
                if sql is not None:sql.delete_session(path.stem)
                path.unlink()
                deleted += 1
        return deleted

    def get_image(self, user_id, chat_id, image_id):
        with self.transaction():
            self.expire()
            path = self._path(user_id, chat_id)
            if not path.is_file():
                raise LookupError('Image not found or session expired.')
            record = json.loads(path.read_text())
            entry = next((item for item in record['images'] if item['id'] == image_id), None)
            if entry is None:
                raise LookupError('Image not found.')
            image = (self.directory / entry['image']['stored_path']).resolve()
            if image.parent != (self.directory / 'images').resolve() or not image.is_file():
                raise LookupError('Saved image is unavailable.')
            return entry, image
