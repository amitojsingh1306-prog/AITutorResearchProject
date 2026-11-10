"""Verify automatic local graph/MySQL updates without asking a model to generate."""
import json,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.models.chat import Message

checks={}
with tempfile.TemporaryDirectory(prefix='verify-graph-updates-') as tmp:
    settings=Settings(_env_file=None,chroma_path=Path(tmp),mysql_enabled=True,graph_enabled=True,memory_configuration='graph',local_only=True)
    with TestClient(create_app(settings)) as client:
        repo=client.app.state.chat_service._repository;graph=repo.graph_memory
        headers={'X-User-Id':'isolated-graph-verification'}
        try:
            first=client.post('/chat/create',headers=headers,json={}).json()
            other=client.post('/chat/create',headers=headers,json={}).json()
            now=datetime.now(timezone.utc)
            for mid,chat,content in [('v-name',first,'My name is Amitoj.'),('v-study',first,"I'm learning binary search in Python."),('v-other',other,'I prefer short numbered explanations.')]:
                repo.save_message(Message(id=mid,chat_id=chat['id'],session_id=chat['session_id'],user_id=headers['X-User-Id'],role='user',content=content,timestamp=now))
            def sources():return [dict(r) for r in graph.run('MATCH (m:AITutorGraph:SourceMessage {scope:$scope}) RETURN m.message_id AS id,m.content AS content',scope=graph.scope)]
            checks['automatic_source_sync']=len(sources())==3
            facts=[dict(r) for r in graph.run('MATCH (f:AITutorGraph:Fact {scope:$scope,active:true}) RETURN f.kind AS kind,f.value AS value',scope=graph.scope)]
            checks['supported_name_fact']=any(f['kind']=='name' and f['value']=='Amitoj' for f in facts)
            checks['mysql_message_sync']=len(repo.sql_store.documents('messages.json'))==3
            response=client.patch('/chat/'+first['id']+'/messages/v-name',headers=headers,json={'content':'My name is AJ.'})
            checks['update_http_success']=response.status_code==200
            checks['updated_source_in_graph']=any(r['id']=='v-name' and r['content']=='My name is AJ.' for r in sources())
            checks['old_source_removed']=all('Amitoj' not in r['content'] for r in sources())
            response=client.post('/chat/'+first['id']+'/forget',headers=headers,json={'target':'this conversation'})
            checks['forget_http_success']=response.status_code==200
            checks['forgotten_graph_sources_removed']={r['id'] for r in sources()}=={'v-other'}
            checks['other_chat_preserved']=len(repo.list_messages(other['id'],headers['X-User-Id']))==1
            checks['forgotten_mysql_messages_removed']=set(repo.sql_store.documents('messages.json'))=={'v-other'}
            checks['forgotten_json_messages_removed']={m.id for m in repo.list_user_messages(headers['X-User-Id'])}=={'v-other'}
        finally:
            graph.clear_namespace();repo.sql_store.clear_namespace()
            checks['graph_namespace_cleanup']=not sources()
report={'passed':all(checks.values()),'checks':checks,'scope':'Isolated live Neo4j/MySQL; repository saves plus actual FastAPI patch/forget routes; no model generation','notes':['Graph sources are user messages. Only supported rule-extracted assertions become facts.','This does not test Chroma, OCR, or distributed failure recovery.']}
out=ROOT/'benchmark_outputs/graph_auto_update_verification.json';out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));sys.exit(0 if report['passed'] else 1)
