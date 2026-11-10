"""Real local Neo4j + Qwen test; removes its isolated graph namespace afterward."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,timedelta,timezone
import json,tempfile
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.config import Settings
from backend.models.chat import Message

ROOT=Path(__file__).resolve().parents[1]

def main():
    report={}
    with tempfile.TemporaryDirectory(prefix='tutor-graph-proof-') as tmp:
        settings=Settings(_env_file=None,chroma_path=Path(tmp),graph_enabled=True,memory_configuration='graph')
        with TestClient(create_app(settings)) as client:
            service=client.app.state.chat_service;repo=service._repository;graph=repo.graph_memory
            try:
                headers={'X-User-Id':'graph-proof-A'}
                chat=client.post('/chat/create',headers=headers,json={}).json()
                def seed(text,index,user='graph-proof-A',chat_value=chat):
                    item=Message(id=f'{user}-{index}',chat_id=chat_value['id'],user_id=user,
                        session_id=chat_value['session_id'],role='user',content=text,
                        timestamp=datetime.now(timezone.utc)+timedelta(seconds=index))
                    repo.save_message(item);return item
                original=seed('My name is Amitoj.',0)
                seed("I'm learning binary search in Python.",1)
                difficulty=seed('I keep confusing low, high and mid.',2)
                seed('My name is AJ.',3)
                foreign=client.post('/chat/create',headers={'X-User-Id':'graph-proof-B'},json={}).json()
                seed('My name is PRIVATE_B.',0,user='graph-proof-B',chat_value=foreign)
                next_chat=client.post('/chat/create',headers=headers,json={}).json()
                response=client.post(f"/chat/{next_chat['id']}/message",headers=headers,
                    json={'content':"What do I struggle with in the algorithm I'm learning?"})
                assert response.status_code==201,response.text
                reply=response.json()['assistant_message']; trace=reply['memory_trace']
                facts=trace['graph_memory']['facts']
                assert any(f['source_message_id']==difficulty.id and f['used_topic_join'] and f['included_in_prompt'] for f in facts),trace
                assert 'PRIVATE_B' not in reply['content']
                assert 'low' in reply['content'].lower() and 'mid' in reply['content'].lower(),reply
                question=Message(id='probe',chat_id=next_chat['id'],user_id='graph-proof-A',session_id=next_chat['session_id'],role='user',content='What is my name?',timestamp=datetime.now(timezone.utc))
                names,_=graph.retrieve(question)
                assert [n['value'] for n in names]==['AJ'],names
                # Direct source edit and deletion must reconcile the graph.
                repo.save_message(original.model_copy(update={'content':'My name is Superseded Old Name.'}))
                names,_=graph.retrieve(question);assert [n['value'] for n in names]==['AJ']
                saved=repo._read_json_file(repo._message_file);saved.pop(difficulty.id)
                repo._write_json_file(repo._message_file,saved)
                question.content="What do I struggle with in the algorithm I'm learning?"
                remaining,_=graph.retrieve(question)
                assert not any(f['kind']=='difficulty' for f in remaining)
                # Forget only this user's old chat; another learner remains intact.
                manifest_path=repo.session_memory._path('graph-proof-A',chat['id'])
                manifest=json.loads(manifest_path.read_text())
                manifest['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
                manifest_path.write_text(json.dumps(manifest))
                assert repo.session_memory.expire()==1
                assert not manifest_path.exists()
                assert not graph.run('MATCH (s:AITutorGraph:Session {scope:$scope,chat_id:$chat}) RETURN s',scope=graph.scope,chat=chat['id'])
                graph.sync('graph-proof-A')
                assert graph.run('MATCH (l:AITutorGraph:Learner {scope:$scope,user_id:$user}) RETURN l',scope=graph.scope,user='graph-proof-B')
                report={'scope':'Isolated integration test, not LoCoMo scores',
                        'local_neo4j':'PASS','multi_relationship_retrieval':'PASS',
                        'correction_filtering':'PASS','source_delete_sync':'PASS',
                        'user_isolation':'PASS','session_graph_deletion':'PASS',
                        'qwen_answer':reply['content'],'memory_trace':trace}
            finally: graph.clear_namespace()
    output=ROOT/'benchmark_outputs/graph_memory_verification.json'
    output.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
