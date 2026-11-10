"""Exercise actual MySQL, Neo4j, Chroma, local OCR and Qwen in isolated storage."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,timedelta,timezone
import json,tempfile
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.database.chroma_repository import ChromaChatRepository
from backend.models.chat import ChatSummary,Message
from backend.models.learner import LearnerProfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    report={}
    with tempfile.TemporaryDirectory(prefix='tutor-mysql-proof-') as tmp:
        directory=Path(tmp)/'db';legacy=ChromaChatRepository(directory)
        now=datetime.now(timezone.utc)
        chat=ChatSummary(id='legacy-chat',user_id='mysql-A',session_id='legacy-session',title='Migration',created_at=now,updated_at=now)
        legacy.save_chat(chat)
        source=Message(id='legacy-message',chat_id=chat.id,user_id='mysql-A',session_id=chat.session_id,
            role='user',content="My name is Amitoj. I'm learning binary search in Python.",timestamp=now)
        legacy.save_message(source)
        settings=Settings(_env_file=None,chroma_path=directory,mysql_enabled=True,graph_enabled=True)
        with TestClient(create_app(settings)) as client:
            repo=client.app.state.chat_service._repository;sql=repo.sql_store;graph=repo.graph_memory
            try:
                headers={'X-User-Id':'mysql-A'}
                url='/chat/'+chat.id
                assert sql.counts()['messages']==1
                # A missing complete JSON working file can recover from SQL.
                # An explicitly empty JSON object is real state, not a cache miss.
                repo._message_file.unlink()
                assert client.get(url,headers=headers).json()['messages'][0]['content']==source.content
                image=ROOT/'backend/tests/fixtures/binary-search-recall.png'
                uploaded=client.post(url+'/images?filename=binary-search.png',headers=headers,content=image.read_bytes())
                assert uploaded.status_code==201,uploaded.text
                image_id=uploaded.json()['id']
                response=client.post(url+'/message/stream',headers=headers,
                    json={'content':'Which algorithm is discussed in this image?','image_id':image_id})
                assert 'event: done' in response.text,response.text
                saved=client.get(url,headers=headers).json()['messages']
                answer=saved[-1]['content']
                assert 'binary search' in answer.lower(),answer
                assert saved[-1]['memory_trace']['conversation_store']=='json'
                assert saved[-1]['memory_trace']['persistence_mirror']=='mysql'
                with sql.transaction() as cursor:
                    cursor.execute('SELECT embedding_dimension FROM vector_memory_metadata WHERE scope=%s',(sql.scope,))
                    dimensions=[row['embedding_dimension'] for row in cursor.fetchall()]
                assert dimensions and all(d==768 for d in dimensions),dimensions
                # Store enough source messages to exercise summary persistence too.
                for index in range(11):
                    repo.save_message(source.model_copy(update={'id':f'filler-{index}',
                      'content':f'Practice checkpoint {index}: keep this for later.',
                      'timestamp':now+timedelta(seconds=index+1)}))
                current=source.model_copy(update={'id':'summary-probe','content':'What did we discuss?'})
                history=repo.list_messages(chat.id,'mysql-A')
                summary,_,_=client.app.state.chat_service._rolling_summary.context(current,history)
                assert summary
                with sql.transaction() as cursor:
                    cursor.execute('SELECT summary_text FROM conversation_summaries WHERE scope=%s AND session_key=%s',
                                   (sql.scope,repo.session_memory._path('mysql-A',chat.id).stem))
                    assert cursor.fetchone()['summary_text']==summary
                foreign=client.post('/chat/create',headers={'X-User-Id':'mysql-B'},json={}).json()
                repo.save_message(source.model_copy(update={'id':'foreign','chat_id':foreign['id'],'user_id':'mysql-B',
                                                            'session_id':foreign['session_id'],'content':'My name is Other Learner.'}))
                repo.save_learner_profile(LearnerProfile(user_id='mysql-B',name='Other Learner'))
                assert repo.get_learner_profile('mysql-B').name=='Other Learner'
                assert client.get(url,headers={'X-User-Id':'mysql-B'}).status_code==404
                before=sql.counts()
                path=repo.session_memory._path('mysql-A',chat.id)
                record=json.loads(path.read_text());record['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
                repo.session_memory.persist(path,record)
                assert client.get(url,headers=headers).status_code==404
                assert not path.exists()
                after=sql.counts()
                assert after['conversations']==1 and after['messages']==1 and after['image_records']==0,after
                assert not repo.semantic_memory.collection.get(where={'user_id':'mysql-A'})['ids']
                assert not graph.run('MATCH (n:AITutorGraph {scope:$scope,user_id:$user}) RETURN n',scope=graph.scope,user='mysql-A')
                assert client.get('/chat/'+foreign['id'],headers={'X-User-Id':'mysql-B'}).status_code==200
                # A foreign-key failure must roll back the whole SQL document update.
                existing=sql.documents('messages.json')
                invalid=source.model_copy(update={'id':'invalid','chat_id':'does-not-exist'})
                try:sql.save_documents('messages.json',{**existing,'invalid':invalid.model_dump_json()})
                except Exception:pass
                else:raise AssertionError('Expected foreign-key failure')
                assert sql.documents('messages.json')==existing
                report={'scope':'Isolated integration check, not LoCoMo scores','json_working_memory_mysql_recovery':'PASS',
                    'json_migration':'PASS','sql_rollback':'PASS','local_ocr_qwen':'PASS',
                    'actual_embedding_dimensions':sorted(set(dimensions)), 'summary_persistence':'PASS',
                    'session_deletion_all_active_stores':'PASS','user_isolation':'PASS',
                    'qwen_answer':answer,'sql_counts_before_expiry':before,'sql_counts_after_expiry':after}
            finally:
                graph.clear_namespace();sql.clear_namespace()
    path=ROOT/'benchmark_outputs/mysql_storage_verification.json'
    path.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
