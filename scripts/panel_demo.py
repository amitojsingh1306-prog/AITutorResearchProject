"""Clean end-to-end local tutor demonstration with evidence and real-store checks.

Uses temporary namespaces, not your private conversations. The reference checks
below are diagnostics and never enter the model's prompt. No LoCoMo score is
claimed for this custom tutor scenario.
"""
import sys,json,tempfile,time,math,re
from pathlib import Path
from datetime import datetime,timedelta,timezone
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.config import Settings
from backend.models.chat import Message


def cosine(a,b):
    return sum(x*y for x,y in zip(a,b))/(math.sqrt(sum(x*x for x in a))*math.sqrt(sum(y*y for y in b)))


def missing(text):
    return bool(re.search(r"(?:don'?t|do not|not) (?:have|know|recall)|(?:not|never) (?:mentioned|provided|saved|specified)|no (?:information|record|university|name)",text,re.I))


def main():
    report={'scope':'Custom local tutor API demonstration, not official LoCoMo','observations':[], 'checks':{},'generation_note':'Supported tutor answers use Qwen; explicit updates/forgetting and unsupported identity abstention use backend policy.'}
    base=Settings()
    report['settings']={'model':base.lmstudio_model,'embedding_model':base.embedding_model,'context_allowance':base.prompt_token_budget,'output_cap':128}
    with tempfile.TemporaryDirectory(prefix='panel-demo-') as directory:
        settings=Settings(_env_file=None,chroma_path=Path(directory),mysql_enabled=True,graph_enabled=True,
            memory_configuration='hybrid',lmstudio_base_url=base.lmstudio_base_url,
            lmstudio_model=base.lmstudio_model,embedding_model=base.embedding_model,
            prompt_token_budget=base.prompt_token_budget,memory_min_similarity=base.memory_min_similarity)
        with TestClient(create_app(settings)) as client:
            service=client.app.state.chat_service;repo=service._repository
            service._llm_client=replace(service._llm_client,num_predict=128)
            headers={'X-User-Id':'panel-demo-A'}
            try:
                chat=client.post('/chat/create',headers=headers,json={'title':'Panel source session'}).json()
                now=datetime.now(timezone.utc)
                sources=["My name is Amitoj. I'm learning binary search in Python. I prefer short explanations using numbered steps.",
                    'I keep confusing low, high, and mid. Remember that this is my main difficulty.',
                    'My goal is to implement binary search correctly in Python.', 'I have completed arrays.']
                for i,text in enumerate(sources+[f'Practice checkpoint {i}.' for i in range(12)]):
                    repo.save_message(Message(id=f'source-{i}',chat_id=chat['id'],user_id='panel-demo-A',session_id=chat['session_id'],
                        role='user',content=text,timestamp=now-timedelta(minutes=30-i)))
                followup=client.post('/chat/create',headers=headers,json={'title':'Panel follow-up session'}).json()
                url='/chat/'+followup['id']
                def ask(label,question,expected=None,absent=False):
                    started=time.perf_counter();response=client.post(url+'/message',headers=headers,json={'content':question})
                    response.raise_for_status();answer=response.json()['assistant_message']
                    trace=answer.get('memory_trace') or {}
                    checks=({'expected_terms_present':all(t in answer['content'].lower() for t in expected)} if expected is not None else {'backend_action_completed':trace.get('memory_action',{}).get('status')=='completed'})
                    if absent:checks={'acknowledges_missing_information':missing(answer['content'])}
                    result={'case':label,'question':question,'answer':answer['content'],
                        'generator_used':not (trace.get('generation_used') is False or 'memory_action' in trace),
                        'request_ms':round((time.perf_counter()-started)*1000,2),'diagnostics':checks,'trace':trace}
                    report['observations'].append(result)
                    print('\n'+label+'\nQUESTION: '+question+'\nANSWER: '+answer['content'],flush=True)
                    print('DIAGNOSTICS:',json.dumps(checks),'TIME MS:',result['request_ms'],flush=True)
                    return result
                ask('Cross-session name','What is my name?',['amitoj'])
                ask('Cross-session study','What algorithm am I learning, and in which language?',['binary search','python'])
                ask('Preference','How do I prefer explanations?',['short','number'])
                ask('Goal','What is my learning goal?',['binary search','python'])
                joined=ask('Linked difficulty',"What is my main difficulty in the algorithm I'm learning?",['low','high','mid'])
                report['checks']['topic_join_used']=bool(joined['trace'].get('graph_memory',{}).get('used_topic_join'))
                ask('Completed topic','What topic have I completed?',['array'])
                ask('Unsupported personal fact','Which university do I attend?',absent=True)
                # Independently recompute actual cosine values for stored source
                # vectors, rather than equating scores with model confidence.
                latest=report['observations'][1]
                query=repo.semantic_memory.embed([latest['question']],query=True)[0]
                candidates=latest['trace'].get('retrieved_memories',[])
                numeric=[]
                for item in candidates[:3]:
                    stored=repo.semantic_memory.collection.get(ids=[item['id']],include=['embeddings'])
                    computed=cosine(query,stored['embeddings'][0])
                    numeric.append({'source_id':item['id'],'chroma_similarity':item['cosine_similarity'],
                        'independent_cosine':float(computed),'matches':bool(abs(computed-item['cosine_similarity'])<1e-5),
                        'dimensions':len(query),'query_vector_preview':query[:8]})
                report['cosine_verification']=numeric
                report['checks']['cosine_matches']=bool(numeric) and all(x['matches'] for x in numeric)
                print('\nCOSINE VERIFICATION:',json.dumps(numeric),flush=True)
                ask('Explicit update','Update my name to AJ.')
                ask('Updated fact','What is my name?',['aj'])
                ask('Explicit forgetting','Forget my name.')
                forgotten=ask('After forgetting','What is my name?',absent=True)
                records=repo.list_user_messages('panel-demo-A')
                report['checks']['forgotten_name_absent_from_source']=not any(re.search(r'\b(?:amitoj|aj)\b',m.content,re.I) for m in records)
                report['checks']['forgetting_response_does_not_repeat_name']=not re.search(r'\b(?:amitoj|aj)\b',forgotten['answer'],re.I)
                report['checks']['sql_is_source']=all(r['trace'].get('conversation_store')=='mysql' for r in report['observations'] if r['trace'].get('memory_configuration'))
                report['note']='Term presence and missing-answer wording are transparent diagnostics. Read complete answers before claiming factual correctness. Full UI latency and benchmark generation timing are different measurements.'
            finally:
                repo.graph_memory.clear_namespace();repo.sql_store.clear_namespace()
                report['cleanup']={'neo4j_namespace':'removed','mysql_namespace':'removed'}
    path=ROOT/'benchmark_outputs/panel_demo.json';path.write_text(json.dumps(report,indent=2))
    print('\nSaved:',path,flush=True)
    print('STRUCTURAL CHECKS:',json.dumps(report['checks']),flush=True)
    return 0 if all(report['checks'].values()) and all(all(item['diagnostics'].values()) for item in report['observations']) else 1

if __name__=='__main__':raise SystemExit(main())
