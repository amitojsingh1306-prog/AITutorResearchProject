import json
import pytest
from backend.database.mysql_repository import MySQLChatRepository


class Store:
    def __init__(self):self.tables={};self.records={};self.fail=False
    def has_scope(self):return False
    def migrate_once(self,original):self.tables=original;return False
    def documents(self,name):return self.tables.get(name,{})
    def save_documents(self,name,payload):
        if self.fail:raise RuntimeError('SQL temporarily unavailable')
        self.tables[name]=payload
    def sessions(self):return self.records
    def save_session(self,key,record):self.records[key]=record


def test_reads_working_json_and_replays_failed_mirror_before_next_read(tmp_path):
    store=Store();repo=MySQLChatRepository(tmp_path,store)
    payload={'m':json.dumps({'id':'m','content':'retained'})}
    store.fail=True
    with pytest.raises(RuntimeError):repo._write_json_file(repo._message_file,payload)
    assert json.loads(repo._message_file.read_text())==payload
    assert list(repo._pending_directory.glob('*.json'))
    store.fail=False
    assert repo._read_json_file(repo._message_file)==payload
    assert store.documents('messages.json')==payload
    assert not list(repo._pending_directory.glob('*.json'))
    store.tables['messages.json']={}
    assert repo._read_json_file(repo._message_file)==payload
    repo._write_json_file(repo._message_file,{})
    assert not store.documents('messages.json')


def test_session_json_is_written_before_mysql_and_pending_session_retries(tmp_path):
    store=Store();repo=MySQLChatRepository(tmp_path,store)
    path=repo.session_memory._path('u','c')
    record={'user_id':'u','chat_id':'c','rolling_summary':'Supported source excerpt'}
    original=store.save_session
    def unavailable(*args):raise RuntimeError('SQL unavailable')
    store.save_session=unavailable
    with pytest.raises(RuntimeError):repo.persist_session_record(path,record)
    assert json.loads(path.read_text())==record
    store.save_session=original
    repo.resume_sync()
    assert store.records[path.stem]==record
