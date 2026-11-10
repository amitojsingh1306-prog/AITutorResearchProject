import sys,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from datetime import datetime,timezone,timedelta
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.models.chat import Message
from backend.database.mysql_repository import MySQLChatRepository
report={}
with tempfile.TemporaryDirectory(prefix='blueprint-mysql-proof-') as tmp:
    settings=Settings(_env_file=None,chroma_path=Path(tmp),mysql_enabled=True,graph_enabled=True,memory_configuration='hybrid',working_memory_message_limit=2,prompt_token_budget=6144)
    with TestClient(create_app(settings)) as client:
        service=client.app.state.chat_service;repo=service._repository;sql=repo.sql_store
        h={'X-User-Id':'blueprint-integration'}
        chat=client.post('/chat/create',headers=h,json={}).json();url='/chat/'+chat['id']
        other=client.post('/chat/create',headers=h,json={}).json()
        now=datetime.now(timezone.utc)
        try:
            for i,text in enumerate(['My name is Amitoj.','I prefer short numbered explanations.',"I'm learning binary search in Python.",'I keep confusing low, high and mid.']):
                repo.save_message(Message(id=f'blueprint-source-{i}',chat_id=chat['id'],user_id=h['X-User-Id'],session_id=chat['session_id'],role='user',content=text,timestamp=now+timedelta(microseconds=i)))
            record=json.loads(repo.session_memory._path(h['X-User-Id'],chat['id']).read_text())
            assert record['rolling_summary']
            with sql.transaction() as cursor:
                cursor.execute('SELECT summary_text FROM conversation_summaries WHERE scope=%s AND session_key=%s',(sql.scope,repo.session_memory._path(h['X-User-Id'],chat['id']).stem))
                assert cursor.fetchone()['summary_text']==record['rolling_summary']
            report['summary_automatically_saved_in_json_and_mysql']=True
            for key,text,expected in [('normal','Explain binary search briefly.','normal_content'),('summary','Summarize our conversation.','conversation_summary')]:
                response=client.post(url+'/message',headers=h,json={'content':text})
                assert response.status_code==201,response.text
                msg=response.json()['assistant_message'];trace=msg['memory_trace']
                assert trace['response_blueprint']['template']==expected
                assert trace['conversation_store']=='json' and trace['persistence_mirror']=='mysql'
                report[key]={'answer':msg['content'],'template':expected}
                print(key+': '+msg['content'],flush=True)
            documents=json.loads(repo._message_file.read_text())
            assert {k:json.loads(v) for k,v in sql.documents('messages.json').items()}=={k:json.loads(v) for k,v in documents.items()}
            recovered=MySQLChatRepository(Path(tmp),sql)
            assert recovered.list_messages(chat['id'],h['X-User-Id'])
            report['restart_keeps_json_and_session_mapping']=True
            r=client.patch(url+'/messages/blueprint-source-0',headers=h,json={'content':'My name is AJ.'})
            assert r.status_code==200,r.text
            assert 'My name is AJ.' in str(sql.documents('messages.json'))
            report['edit_synchronizes_mysql']=True
            r=client.post(url+'/message',headers=h,json={'content':'ok forget abt this conversation'})
            assert r.status_code==201,r.text
            documents=sql.documents('messages.json')
            assert not any('blueprint-source-' in key for key in documents)
            assert 'binary search' not in json.dumps(client.get(url,headers=h).json()).lower()
            assert not repo.semantic_memory.collection.get(ids=[f'blueprint-source-{i}' for i in range(4)])['ids']
            assert client.get('/chat/'+other['id'],headers=h).status_code==200
            record=json.loads(repo.session_memory._path(h['X-User-Id'],chat['id']).read_text())
            assert 'binary search' not in record['rolling_summary'].lower()
            report['forget_clears_sources_vectors_summary_and_mysql']=True
            report['other_conversation_preserved']=True
            assert not list(repo._pending_directory.glob('*.json'))
            report['pending_mysql_sync_empty']=True
        finally:
            repo.graph_memory.clear_namespace();sql.clear_namespace()
report['scope']='Isolated functional integration, not a LoCoMo score or universal model-format guarantee.'
(ROOT/'benchmark_outputs/response_blueprint_verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
