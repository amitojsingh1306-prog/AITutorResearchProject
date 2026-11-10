"""Local MySQL source records; vectors and graph relationships stay in their stores."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


SCHEMA = [
'''CREATE TABLE IF NOT EXISTS storage_scopes (
 scope CHAR(24) PRIMARY KEY, migrated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6))''',
'''CREATE TABLE IF NOT EXISTS conversations (
 scope CHAR(24) NOT NULL,id VARCHAR(120) NOT NULL,user_id VARCHAR(120) NOT NULL,
 title VARCHAR(120) NOT NULL,session_id VARCHAR(120) NOT NULL,payload JSON NOT NULL,
 PRIMARY KEY(scope,id),UNIQUE KEY conversation_owner(scope,id,user_id),KEY user_chats(scope,user_id))''',
'''CREATE TABLE IF NOT EXISTS messages (
 scope CHAR(24) NOT NULL,id VARCHAR(120) NOT NULL,chat_id VARCHAR(120) NOT NULL,user_id VARCHAR(120) NOT NULL,
 role VARCHAR(20) NOT NULL,payload JSON NOT NULL,PRIMARY KEY(scope,id),KEY user_messages(scope,user_id),
 CONSTRAINT fk_message_owner FOREIGN KEY(scope,chat_id,user_id) REFERENCES conversations(scope,id,user_id) ON DELETE CASCADE)''',
'''CREATE TABLE IF NOT EXISTS learner_profiles (
 scope CHAR(24) NOT NULL,user_id VARCHAR(120) NOT NULL,payload JSON NOT NULL,PRIMARY KEY(scope,user_id))''',
'''CREATE TABLE IF NOT EXISTS memory_sessions (
 scope CHAR(24) NOT NULL,session_key CHAR(64) NOT NULL,user_id VARCHAR(120) NOT NULL,chat_id VARCHAR(120),
 expires_at DATETIME(6) NOT NULL,blueprint JSON NOT NULL,PRIMARY KEY(scope,session_key),
 CONSTRAINT fk_session_owner FOREIGN KEY(scope,chat_id,user_id) REFERENCES conversations(scope,id,user_id) ON DELETE CASCADE)''',
'''CREATE TABLE IF NOT EXISTS conversation_summaries (
 scope CHAR(24) NOT NULL,session_key CHAR(64) NOT NULL,summary_text TEXT NOT NULL,metadata JSON NOT NULL,
 PRIMARY KEY(scope,session_key),CONSTRAINT fk_summary_session FOREIGN KEY(scope,session_key)
 REFERENCES memory_sessions(scope,session_key) ON DELETE CASCADE)''',
'''CREATE TABLE IF NOT EXISTS image_records (
 scope CHAR(24) NOT NULL,id CHAR(32) NOT NULL,session_key CHAR(64) NOT NULL,user_id VARCHAR(120) NOT NULL,
 metadata JSON NOT NULL,PRIMARY KEY(scope,id),CONSTRAINT fk_image_session FOREIGN KEY(scope,session_key)
 REFERENCES memory_sessions(scope,session_key) ON DELETE CASCADE)''',
'''CREATE TABLE IF NOT EXISTS vector_memory_metadata (
 scope CHAR(24) NOT NULL,message_id VARCHAR(120) NOT NULL,collection_name VARCHAR(120) NOT NULL,
 embedding_model VARCHAR(200) NOT NULL,embedding_dimension INT NOT NULL,content_hash CHAR(64) NOT NULL,
 last_synced_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),PRIMARY KEY(scope,message_id,collection_name),
 CONSTRAINT fk_vector_message FOREIGN KEY(scope,message_id) REFERENCES messages(scope,id) ON DELETE CASCADE)''',
]
TABLES={'chats.json':('conversations','id'),'messages.json':('messages','id'),
        'learner_profiles.json':('learner_profiles','user_id')}


class MySQLStore:
    def __init__(self, directory: Path, credentials: dict):
        if credentials.get('host') not in {'127.0.0.1','localhost','::1'}:
            raise ValueError('MySQL storage only permits a local server.')
        from mysql.connector.pooling import MySQLConnectionPool
        self.scope=hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest()[:24]
        self.pool=MySQLConnectionPool(pool_name='aitutor_'+self.scope,pool_size=3,
            pool_reset_session=True,connection_timeout=5,autocommit=False,charset='utf8mb4',**credentials)
        with self.transaction() as cursor:
            for statement in SCHEMA:cursor.execute(statement)

    @contextmanager
    def transaction(self):
        connection=self.pool.get_connection();cursor=connection.cursor(dictionary=True)
        try:
            yield cursor
            connection.commit()
        except BaseException:
            connection.rollback();raise
        finally:
            cursor.close();connection.close()

    def documents(self,filename):
        table,key=TABLES[filename]
        with self.transaction() as cursor:
            cursor.execute(f'SELECT {key},payload FROM {table} WHERE scope=%s',(self.scope,))
            return {row[key]:row['payload'] if isinstance(row['payload'],str) else json.dumps(row['payload']) for row in cursor.fetchall()}

    def _save_documents(self,cursor,filename,documents):
        table,key=TABLES[filename]
        for identifier,serialized in documents.items():
            data=json.loads(serialized)
            if data[key]!=identifier:raise ValueError('SQL document ID does not match its record key.')
            if table=='conversations':
                fields=['id','user_id','title','session_id']
            elif table=='messages':fields=['id','chat_id','user_id','role']
            else:fields=['user_id']
            columns=['scope',*fields,'payload']
            values=[self.scope,*[data[field] for field in fields],serialized]
            updates=','.join(f'{field}=new.{field}' for field in [*fields,'payload'] if field!=key)
            cursor.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(['%s']*len(columns))}) AS new ON DUPLICATE KEY UPDATE {updates}",values)
        cursor.execute(f'SELECT {key} FROM {table} WHERE scope=%s',(self.scope,))
        removed=[(self.scope,row[key]) for row in cursor.fetchall() if row[key] not in documents]
        if removed:cursor.executemany(f'DELETE FROM {table} WHERE scope=%s AND {key}=%s',removed)

    def save_documents(self,filename,documents):
        with self.transaction() as cursor:self._save_documents(cursor,filename,documents)

    def migrate_once(self,documents):
        with self.transaction() as cursor:
            cursor.execute('SELECT scope FROM storage_scopes WHERE scope=%s',(self.scope,))
            if cursor.fetchone():return False
            for filename in TABLES:self._save_documents(cursor,filename,documents[filename])
            cursor.execute('INSERT INTO storage_scopes(scope) VALUES(%s)',(self.scope,))
        return True

    def has_scope(self):
        with self.transaction() as cursor:
            cursor.execute('SELECT scope FROM storage_scopes WHERE scope=%s',(self.scope,))
            return cursor.fetchone() is not None

    def save_session(self,key,record):
        expiry=datetime.fromisoformat(record['expires_at']).astimezone(timezone.utc).replace(tzinfo=None)
        with self.transaction() as cursor:
            cursor.execute('''INSERT INTO memory_sessions(scope,session_key,user_id,chat_id,expires_at,blueprint)
              VALUES(%s,%s,%s,%s,%s,%s) AS new ON DUPLICATE KEY UPDATE
              expires_at=new.expires_at,blueprint=new.blueprint''',
              (self.scope,key,record['user_id'],record['chat_id'],expiry,json.dumps(record)))
            cursor.execute('''INSERT INTO conversation_summaries(scope,session_key,summary_text,metadata)
              VALUES(%s,%s,%s,%s) AS new ON DUPLICATE KEY UPDATE summary_text=new.summary_text,metadata=new.metadata''',
              (self.scope,key,record['rolling_summary'],json.dumps(record.get('rolling_summary_meta',{}))))
            cursor.execute('DELETE FROM image_records WHERE scope=%s AND session_key=%s',(self.scope,key))
            for entry in record['images']:
                cursor.execute('INSERT INTO image_records(scope,id,session_key,user_id,metadata) VALUES(%s,%s,%s,%s,%s)',
                               (self.scope,entry['id'],key,record['user_id'],json.dumps(entry)))

    def sessions(self):
        with self.transaction() as cursor:
            cursor.execute('SELECT session_key,blueprint FROM memory_sessions WHERE scope=%s',(self.scope,))
            return {row['session_key']:json.loads(row['blueprint']) for row in cursor.fetchall()}

    def delete_session(self,key):
        with self.transaction() as cursor:
            cursor.execute('DELETE FROM memory_sessions WHERE scope=%s AND session_key=%s',(self.scope,key))

    def embedding_synced(self,message_id,collection,model,dimension,content_hash):
        with self.transaction() as cursor:
            cursor.execute('''INSERT INTO vector_memory_metadata(scope,message_id,collection_name,embedding_model,embedding_dimension,content_hash)
              VALUES(%s,%s,%s,%s,%s,%s) AS new ON DUPLICATE KEY UPDATE embedding_model=new.embedding_model,
              embedding_dimension=new.embedding_dimension,content_hash=new.content_hash,last_synced_at=CURRENT_TIMESTAMP(6)''',
              (self.scope,message_id,collection,model,dimension,content_hash))

    def embedding_ids(self,collection):
        with self.transaction() as cursor:
            cursor.execute('SELECT message_id FROM vector_memory_metadata WHERE scope=%s AND collection_name=%s',
                           (self.scope,collection))
            return {row['message_id'] for row in cursor.fetchall()}

    def counts(self):
        with self.transaction() as cursor:
            result={}
            for table in ['conversations','messages','learner_profiles','memory_sessions','conversation_summaries','image_records','vector_memory_metadata']:
                cursor.execute(f'SELECT COUNT(*) AS n FROM {table} WHERE scope=%s',(self.scope,))
                result[table]=cursor.fetchone()['n']
            return result

    def clear_namespace(self):
        with self.transaction() as cursor:
            cursor.execute('DELETE FROM memory_sessions WHERE scope=%s',(self.scope,))
            cursor.execute('DELETE FROM conversations WHERE scope=%s',(self.scope,))
            cursor.execute('DELETE FROM learner_profiles WHERE scope=%s',(self.scope,))
            cursor.execute('DELETE FROM storage_scopes WHERE scope=%s',(self.scope,))

    def close(self):
        # Connector/Python has no public close-all method for a pool. Drain the
        # private pool only at application shutdown, after requests have stopped.
        while not self.pool._cnx_queue.empty():
            connection=self.pool._cnx_queue.get_nowait();connection.close()
