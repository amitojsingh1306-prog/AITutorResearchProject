"""Real-store edit/delete/forget verification; temporary namespaces only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,timezone
import json,tempfile
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.models.chat import Message
from backend.ocr.local_ocr import OCRResult

ROOT=Path(__file__).resolve().parents[1]

def main():
    report={}
    with tempfile.TemporaryDirectory(prefix='tutor-forget-proof-') as tmp:
        settings=Settings(_env_file=None,chroma_path=Path(tmp),mysql_enabled=True,graph_enabled=True)
        with TestClient(create_app(settings)) as client:
            repo=client.app.state.chat_service._repository;graph=repo.graph_memory;sql=repo.sql_store
            try:
                headers={'X-User-Id':'forget-A'}
                chat=client.post('/chat/create',headers=headers,json={}).json();url='/chat/'+chat['id']
                other=client.post('/chat/create',headers={'X-User-Id':'forget-B'},json={}).json()
                now=datetime.now(timezone.utc)
                source=Message(id='source-A',chat_id=chat['id'],user_id='forget-A',session_id=chat['session_id'],
                    role='user',content="My name is Amitoj. I'm learning binary search in Python.",timestamp=now)
                image=ROOT/'backend/tests/fixtures/binary-search-recall.png'
                # Deliberately labelled OCR fixture: this checks erasure of image
                # evidence, not OCR recognition accuracy (tested separately).
                _,entry=repo.session_memory.add_image(image,OCRResult('My name is Amitoj.',[],1,'fixture'),
                    user_id='forget-A',chat_id=chat['id'])
                source.image_attachment={'id':entry['id'],'filename':'fixture.png','ocr_text':'My name is Amitoj.'}
                repo.save_message(source)
                repo.save_message(source.model_copy(update={'id':'echo-A','role':'assistant','content':'Your name is Amitoj.','image_attachment':None}))
                repo.save_message(source.model_copy(update={'id':'source-B','user_id':'forget-B','chat_id':other['id'],
                    'session_id':other['session_id'],'image_attachment':None}))
                response=client.post(url+'/message/stream',headers=headers,json={'content':'Forget my name.'})
                assert 'event: done' in response.text and 'Amitoj' not in response.text,response.text
                active=client.get(url,headers=headers).json()
                assert 'Amitoj' not in json.dumps(active)
                assert any('binary search' in m['content'] for m in active['messages'])
                assert client.get(url+'/images/'+entry['id'],headers=headers).status_code==404
                index=repo.semantic_memory.collection.get(where={'user_id':'forget-A'},include=['documents'])
                assert all('amitoj' not in d.lower() for d in index['documents'])
                assert not graph.run("MATCH (f:AITutorGraph:Fact {scope:$scope,user_id:'forget-A',kind:'name'}) RETURN f",scope=graph.scope)
                assert graph.run("MATCH (f:AITutorGraph:Fact {scope:$scope,user_id:'forget-B',kind:'name'}) RETURN f",scope=graph.scope)
                for record in sql.sessions().values():
                    if record['user_id']=='forget-A':assert 'Amitoj' not in json.dumps(record)
                assert sql.counts()['image_records']==0
                response=client.post(url+'/message',headers=headers,json={'content':'What is my name?'})
                assert response.status_code==201,response.text
                forgotten_reply=response.json()['assistant_message']['content']
                assert 'amitoj' not in forgotten_reply.lower(),forgotten_reply
                response=client.post(url+'/message',headers=headers,json={'content':'Update my name to AJ.'})
                assert response.status_code==201,response.text
                updated_id=response.json()['user_message']['id']
                response=client.post(url+'/message',headers=headers,json={'content':'What is my name?'})
                assert response.status_code==201,response.text
                updated_reply=response.json()['assistant_message']['content']
                assert 'AJ' in updated_reply,updated_reply
                assert client.patch(url+'/messages/'+updated_id,headers={'X-User-Id':'forget-B'},json={'content':'wrong'}).status_code==404
                response=client.patch(url+'/messages/'+updated_id,headers=headers,json={'content':'My name is Aman.'})
                assert response.status_code==200,response.text
                assert not any('AJ' in m.content for m in repo.list_messages(chat['id'],'forget-A'))
                assert client.delete(url+'/messages/'+updated_id,headers=headers).status_code==200
                assert 'Aman' not in json.dumps(client.get(url,headers=headers).json())
                assert client.delete(url,headers=headers).status_code==200
                assert client.get(url,headers=headers).status_code==404
                assert client.get('/chat/'+other['id'],headers={'X-User-Id':'forget-B'}).status_code==200
                assert not repo.semantic_memory.collection.get(where={'user_id':'forget-A'})['ids']
                report={'scope':'Isolated integration check, not a benchmark score',
                    'mysql_source_redaction':'PASS','chroma_removal':'PASS','neo4j_removal':'PASS',
                    'summary_and_trace_cleanup':'PASS','owned_image_cleanup':'PASS','other_user_preserved':'PASS',
                    'chat_forget_command':'PASS','chat_update_command':'PASS','patch_message':'PASS',
                    'delete_message':'PASS','delete_chat':'PASS',
                    'qwen_after_forgetting':forgotten_reply,'qwen_after_update':updated_reply}
            finally:graph.clear_namespace();sql.clear_namespace()
    path=ROOT/'benchmark_outputs/memory_forgetting_verification.json'
    path.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
