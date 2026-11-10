"""Fresh live-model chat-route check, isolated from the user's conversations."""
import json,sys,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
checks={};turns=[]
with tempfile.TemporaryDirectory(prefix='live-tutor-review-') as tmp:
    settings=Settings(_env_file=None,chroma_path=Path(tmp),mysql_enabled=True,graph_enabled=True,memory_configuration='hybrid',local_only=True)
    with TestClient(create_app(settings)) as client:
        repo=client.app.state.chat_service._repository;headers={'X-User-Id':'isolated-live-tutor-review'}
        try:
            chat=client.post('/chat/create',headers=headers,json={}).json();url='/chat/'+chat['id']
            def ask(question):
                start=time.perf_counter();response=client.post(url+'/message/stream',headers=headers,json={'content':question})
                elapsed=(time.perf_counter()-start)*1000
                if response.status_code!=200:raise RuntimeError(f'Chat HTTP status {response.status_code}: {response.text[:200]}')
                events=[]
                for block in response.text.split('\n\n'):
                    lines=block.splitlines();name=next((line[7:] for line in lines if line.startswith('event: ')),None);data=next((line[6:] for line in lines if line.startswith('data: ')),None)
                    if data:events.append((name,json.loads(data)))
                failure=next((data for name,data in events if name=='error'),None)
                if failure:raise RuntimeError(f'Stream error: {failure}')
                done=next((data for name,data in events if name=='done'),None)
                if not done:raise RuntimeError('Stream did not finish with persisted done event')
                result=done;answer=result['assistant_message']['content']
                turns.append({'question':question,'answer':answer,'route_request_ms':elapsed,'memory_trace':result['assistant_message'].get('memory_trace')})
                print(question,'=>',answer[:200],flush=True);return result
            source="My name is Amitoj. I'm learning binary search in Python. I prefer short explanations using numbered steps."
            ask(source)
            source_id=next(m.id for m in repo.list_messages(chat['id'],headers['X-User-Id']) if m.role=='user' and m.content==source)
            answer=ask('What did I tell you about my name, what I am learning, and how I prefer explanations?')['assistant_message']['content'].lower()
            checks['requested_learner_facts_present']=all(s in answer for s in ['amitoj','binary search','python']) and ('number' in answer or 'step' in answer)
            checks['mysql_source_saved']=source_id in repo.sql_store.documents('messages.json')
            checks['graph_source_saved']=bool(repo.graph_memory.run('MATCH (m:AITutorGraph:SourceMessage {scope:$scope,message_id:$mid}) RETURN m',scope=repo.graph_memory.scope,mid=source_id))
            data=repo.semantic_memory.collection.get(ids=[source_id],include=['embeddings'])
            checks['source_vector_saved']=bool(data['ids']) and len(data['embeddings'][0])==768
            update=client.patch(url+'/messages/'+source_id,headers=headers,json={'content':"My name is AJ. I'm learning binary search in Python. I prefer short explanations using numbered steps."})
            checks['correction_route_success']=update.status_code==200
            corrected=ask('What is my name?')['assistant_message']['content']
            checks['corrected_name_answer']='AJ' in corrected and 'Amitoj' not in corrected
            forget=ask('ok forget abt this conversation')['assistant_message']['content']
            checks['forget_acknowledged']='forget' in forget.lower() or 'remov' in forget.lower() or 'clear' in forget.lower()
            checks['source_removed_from_json']=source_id not in {m.id for m in repo.list_user_messages(headers['X-User-Id'])}
            checks['source_removed_from_mysql']=source_id not in repo.sql_store.documents('messages.json')
            checks['source_removed_from_chroma']=not repo.semantic_memory.collection.get(ids=[source_id])['ids']
            checks['source_removed_from_graph']=not repo.graph_memory.run('MATCH (m:AITutorGraph:SourceMessage {scope:$scope,message_id:$mid}) RETURN m',scope=repo.graph_memory.scope,mid=source_id)
            after=ask('What were we talking about?')['assistant_message']['content'].lower()
            checks['forgotten_topic_not_recalled']='binary search' not in after and 'amitoj' not in after
        finally:
            repo.graph_memory.clear_namespace();repo.sql_store.clear_namespace()
report={'passed':all(checks.values()),'checks':checks,'turns':turns,'scope':'Actual FastAPI /message/stream and patch routes with local Qwen/Nomic and isolated JSON/MySQL/Chroma/Neo4j','note':'Integration check of specific facts and mutations; not official LoCoMo or a general factual-accuracy measurement.'}
out=ROOT/'benchmark_outputs/live_tutor_route_verification.json';out.write_text(json.dumps(report,indent=2));print(json.dumps(checks,indent=2));sys.exit(0 if report['passed'] else 1)
