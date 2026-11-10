"""Verify real JSON-to-MySQL mirroring and mutation routes in an isolated scope."""
from _common import check_main,Settings,Message,USER
from pathlib import Path
from datetime import datetime,timezone
import tempfile,json
from fastapi.testclient import TestClient
from backend.main import create_app

def main():
    print('Production code: MySQLChatRepository._write_json_file(), MySQLStore, FastAPI patch/delete routes.',flush=True)
    with tempfile.TemporaryDirectory(prefix='verify-mysql-') as directory:
        settings=Settings(_env_file=None,chroma_path=Path(directory),mysql_enabled=True,graph_enabled=False,memory_configuration='buffer')
        with TestClient(create_app(settings)) as client:
            repo=client.app.state.chat_service._repository
            try:
                headers={'X-User-Id':USER};chat=client.post('/chat/create',headers=headers,json={}).json();url='/chat/'+chat['id']
                source=Message(id='mysql-source',chat_id=chat['id'],user_id=USER,session_id=chat['session_id'],role='user',content='My name is Amitoj.',timestamp=datetime.now(timezone.utc))
                repo.save_message(source)
                saved=json.loads(repo.sql_store.documents('messages.json')[source.id])
                assert saved['content']==source.content
                print('SQL SAVED:',saved['id'],saved['content'])
                update=client.patch(url+'/messages/'+source.id,headers=headers,json={'content':'My name is AJ.'});assert update.status_code==200
                changed=json.loads(repo.sql_store.documents('messages.json')[source.id]);assert changed['content']=='My name is AJ.'
                print('SQL UPDATED:',changed['content'])
                removed=client.delete(url+'/messages/'+source.id,headers=headers);assert removed.status_code==200
                assert source.id not in repo.sql_store.documents('messages.json')
                print('SQL SOURCE DELETED: YES')
            finally:
                repo.sql_store.clear_namespace()
    print('Temporary SQL scope cleaned. No model generation, no changes to your saved chats.')

if __name__=='__main__':check_main(main)
