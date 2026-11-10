"""JSON working memory with a recoverable local MySQL persistence mirror.

Qwen receives text assembled by ChatService, never a database connection.
Pending writes are replayed under the same session/file lock before reads.
"""
import json
from pathlib import Path
import shutil

from backend.database.chroma_repository import ChromaChatRepository
from backend.database.mysql_store import MySQLStore,TABLES
from backend.ocr.image_memory import write_record


class MySQLChatRepository(ChromaChatRepository):
    def __init__(self,persistence_path:Path,store:MySQLStore):
        self.sql_store=store
        super().__init__(persistence_path)
        self._pending_directory=persistence_path/'pending_mysql_sync'
        self._pending_directory.mkdir(exist_ok=True,mode=0o700)
        with self.session_memory.transaction():
            imported=False
            if not store.has_scope():
                original={}
                for name in TABLES:
                    path=persistence_path/name
                    data=json.loads(path.read_text()) if path.exists() else {}
                    if not isinstance(data,dict):raise ValueError(f'Invalid legacy JSON store: {name}')
                    original[name]={key:value if isinstance(value,str) else json.dumps(value) for key,value in data.items()}
                imported=store.migrate_once(original)
            if imported:
                backup=persistence_path.parent/'.local/mysql_migration_backup'
                backup.mkdir(parents=True,exist_ok=True,mode=0o700)
                for name in TABLES:
                    source=persistence_path/name
                    if source.exists() and not (backup/name).exists():shutil.copy2(source,backup/name)
                for path in self.session_memory.directory.glob('*.json'):
                    store.save_session(path.stem,json.loads(path.read_text()))
            self.resume_sync()
            # Preserve the JSON working copy. SQL is recovery storage only if
            # a complete file is missing; never overwrite a valid newer JSON.
            for name in TABLES:
                if not (persistence_path/name).exists():
                    write_record(persistence_path/name,store.documents(name))
            for key,record in store.sessions().items():
                path=self.session_memory.directory/f'{key}.json'
                if not path.exists():write_record(path,record)

    def resume_sync(self):
        # Whole operation snapshots make crashes before/after the JSON write
        # replayable. The marker is removed only after MySQL confirms commit.
        order={'chats.json':0,'messages.json':1,'learner_profiles.json':2}
        paths=sorted(self._pending_directory.glob('*.json'),key=lambda p:(order.get(p.name,3),p.name))
        for pending in paths:
            operation=json.loads(pending.read_text())
            if operation['kind']=='documents':
                name=operation['name']
                if name not in TABLES:raise ValueError('Invalid pending MySQL table')
                write_record(self._message_file.parent/name,operation['payload'])
                self.sql_store.save_documents(name,operation['payload'])
            else:
                key=operation['key']
                if len(key)!=64 or any(c not in '0123456789abcdef' for c in key):
                    raise ValueError('Invalid pending session key')
                write_record(self.session_memory.directory/f'{key}.json',operation['payload'])
                self.sql_store.save_session(key,operation['payload'])
            pending.unlink()

    def _read_json_file(self,path):
        if hasattr(self,'_pending_directory'):
            with self.session_memory.transaction():
                self.resume_sync()
                if path.name in TABLES and not path.exists():
                    write_record(path,self.sql_store.documents(path.name))
        return ChromaChatRepository._read_json_file(path)

    def _write_json_file(self,path,payload):
        if path.name not in TABLES:
            write_record(path,payload)
            return
        with self.session_memory.transaction():
            self.resume_sync()
            pending=self._pending_directory/path.name
            write_record(pending,{'kind':'documents','name':path.name,'payload':payload})
            self.resume_sync()

    def persist_session_record(self,path,record):
        with self.session_memory.transaction():
            self.resume_sync()
            pending=self._pending_directory/f'{path.stem}.json'
            write_record(pending,{'kind':'session','key':path.stem,'payload':record})
            self.resume_sync()
