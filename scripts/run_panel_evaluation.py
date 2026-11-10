"""Repeated four-mode LoCoMo subset evaluation using current production context code.

Uses real isolated MySQL, optional Neo4j/Chroma, and local LM Studio. This is an
offline context-builder evaluation, not an HTTP endpoint throughput benchmark.
Only source dialogue enters memory. Predictions and references never do.
"""
from __future__ import annotations
import argparse, hashlib, json, platform, random, statistics, subprocess, sys
import tempfile, time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import httpx
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.models.chat import ChatSummary, Message
from backend.memory.semantic_chat import token_upper_bound
from backend.utils.local_endpoints import require_loopback
from scripts.run_official_locomo import conversation_messages, select_questions, load_official_scorer

MODES=('buffer','summary','vector','graph')
CATEGORIES={1:'multi_hop',2:'temporal',3:'open_domain',4:'single_hop',5:'adversarial_abstention'}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select_pairs(samples, limit, per_category):
    return [(sample,index,qa) for sample in samples[:limit or None]
            for index,qa in select_questions(sample['qa'],per_category)]


def summarize(rows):
    output={}
    for mode in MODES:
        selected=[r for r in rows if r['mode']==mode]
        valid=[r for r in selected if 'official_score' in r]
        avg=lambda key,rs:statistics.mean(r[key] for r in rs if isinstance(r.get(key),(float,int))) if any(isinstance(r.get(key),(float,int)) for r in rs) else None
        f1=[r for r in valid if r['category']!=5]; abstain=[r for r in valid if r['category']==5]
        output[mode]={'attempted':len(selected),'completed':len(valid),'errors':len(selected)-len(valid),
            'mean_answer_f1_categories_1_4':avg('official_score',f1),
            'abstention_phrase_score_category_5':avg('official_score',abstain),
            'mean_generation_request_ms':avg('generation_ms',valid),
            'mean_context_build_ms':avg('context_build_ms',valid),
            'mean_actual_input_tokens':avg('actual_input_tokens',valid),
            'categories':{str(c):{'name':CATEGORIES[c],'count':sum(r['category']==c for r in valid),
                'score':avg('official_score',[r for r in valid if r['category']==c])} for c in CATEGORIES}}
    return output


def paired_intervals(rows):
    """Cluster bootstrap conversations, preserving repeated questions within each."""
    lookup={(r['sample_id'],r['qa_index'],r['repeat'],r['mode']):r for r in rows if 'official_score' in r and r['category']!=5}
    result={}
    for mode in MODES[1:]:
        clusters=defaultdict(list)
        for (sample,q,repeat,m),row in lookup.items():
            base=lookup.get((sample,q,repeat,'buffer'))
            if m==mode and base:clusters[sample].append(row['official_score']-base['official_score'])
        keys=sorted(clusters)
        if not keys:continue
        rng=random.Random(20261107)
        draws=[]
        for _ in range(2000):
            values=[v for key in rng.choices(keys,k=len(keys)) for v in clusters[key]]
            draws.append(statistics.mean(values))
        draws.sort()
        result[mode]={'paired_f1_difference':statistics.mean(v for values in clusters.values() for v in values),
            'conversation_cluster_bootstrap_95_interval':[draws[49],draws[1949]],
            'conversations':len(keys),'paired_predictions':sum(map(len,clusters.values())),
            'note':'Exploratory interval on this selected subset; not population-wide significance.'}
    return result


def seed_corpus(repo, sample):
    history=conversation_messages(sample,Message)
    user=history[0].user_id;chat_id=history[0].chat_id
    now=datetime.now(timezone.utc)
    chat=ChatSummary(id=chat_id,user_id=user,session_id=history[0].session_id,
        title='Isolated LoCoMo source corpus',created_at=now,updated_at=now)
    repo.save_chat(chat)
    # Bulk source import preserves exact source messages. It avoids invoking an
    # LLM or saving predictions during corpus preparation.
    with repo.session_memory.transaction():
        repo._write_json_file(repo._message_file,{m.id:m.model_dump_json() for m in history})
        repo.session_memory.track_message(history[-1])
    return history


def write_report(out,rows,manifest):
    summary={'completed':len(rows)==manifest['expected_predictions'],
        'scope':'Current context builder; selected official LoCoMo questions; declared modes; repeated local generation',
        'results':summarize(rows),'paired_comparisons':paired_intervals(rows)}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    lines=['# Memory configuration comparison','',summary['scope'],'',
        '| Mode | Completed | Answer F1 1–4 | Abstention 5 | Generation ms | Context ms | Input tokens |',
        '|---|---:|---:|---:|---:|---:|---:|']
    fmt=lambda x:'n/a' if x is None else f'{x:.4f}'
    for mode,r in summary['results'].items():
        lines.append(f"| {mode} | {r['completed']}/{r['attempted']} | {fmt(r['mean_answer_f1_categories_1_4'])} | {fmt(r['abstention_phrase_score_category_5'])} | {fmt(r['mean_generation_request_ms'])} | {fmt(r['mean_context_build_ms'])} | {fmt(r['mean_actual_input_tokens'])} |")
    lines+=['','All modes use the same questions, sources, budget and decoding settings. No answer keys or predictions enter test memory.',
        'The summary strategy is extractive and the graph extractor is rule-based. They are not full implementations of MemGPT, Mem0 or A-MEM.',
        'The first available question per category is a deterministic subset, not a random sample. Category 5 uses the upstream phrase rule, not an LLM judge.',
        'Generation and context timings exclude corpus ingestion. Local HTTP timing is not a cloud API measurement.',
        'This evaluates current context code directly. HTTP save/delete/image integration is checked separately.',
        'Every failure remains in predictions.jsonl. Intervals are clustered by conversation; repeated outputs are not independent new questions.']
    (out/'report.md').write_text('\n'.join(lines)+'\n')


def main():
    global MODES
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--conversation-limit',type=int,default=10)
    parser.add_argument('--questions-per-category',type=int,default=1)
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--modes',nargs='+',choices=(*MODES,'hybrid'),default=list(MODES))
    parser.add_argument('--budget',type=int)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--resume',type=Path,help='Resume exactly the saved question/configuration manifest')
    args=parser.parse_args()
    prior=json.loads((args.resume/'manifest.json').read_text()) if args.resume else None
    if prior:
        args.modes=prior['modes'];args.repeats=prior['repeats'];args.budget=prior['settings']['budget']
        args.conversation_limit=0
        args.questions_per_category=max(sum(q['sample_id']==sid and q['category']==category for q in prior['selected_questions']) for sid in {q['sample_id'] for q in prior['selected_questions']} for category in CATEGORIES)
    if args.repeats<1 or args.conversation_limit<0 or args.questions_per_category<1:parser.error('Invalid scope')
    MODES=tuple(dict.fromkeys(args.modes))
    base=Settings()
    if args.budget is not None:
        if args.budget<512:parser.error('Budget must be at least 512')
        base=base.model_copy(update={'prompt_token_budget':args.budget})
    if prior:
        base=base.model_copy(update={'lmstudio_model':prior['settings']['model'],'embedding_model':prior['settings']['embedding_model'],'memory_min_similarity':prior['settings']['cutoff'],'working_memory_message_limit':prior['settings']['recent_message_limit']})
    require_loopback(base.lmstudio_base_url)
    data=ROOT/'benchmark_data/locomo/locomo10.json';scorer_path=ROOT/'benchmark_data/locomo/upstream_evaluation.py'
    samples=json.loads(data.read_text());pairs=select_pairs(samples,args.conversation_limit,args.questions_per_category)
    if prior:
        approved={(q['sample_id'],q['qa_index']) for q in prior['selected_questions']}
        pairs=[(s,i,q) for s,i,q in pairs if (s['sample_id'],i) in approved]
    chosen={s['sample_id'] for s,_,_ in pairs};samples=[s for s in samples if s['sample_id'] in chosen]
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=args.resume or args.output or ROOT/'benchmark_outputs/panel'/stamp;out.mkdir(parents=True,exist_ok=bool(prior))
    scorer=load_official_scorer(scorer_path)
    with httpx.Client(timeout=180,trust_env=False,follow_redirects=False) as http:
        models=http.get(base.lmstudio_base_url+'/models');models.raise_for_status()
        ids=[item['id'] for item in models.json()['data']]
        for name in (base.lmstudio_model,base.embedding_model):
            if name not in ids:raise RuntimeError(f'Required local model unavailable: {name}')
        if not prior:
            manifest={'created_utc':stamp,'dataset_source':'https://github.com/snap-research/locomo',
                'dataset_sha256':digest(data),'scorer_sha256':digest(scorer_path),
                'selected_questions':[{'sample_id':s['sample_id'],'qa_index':i,'category':q['category']} for s,i,q in pairs],
                'unique_questions':len(pairs),'conversations':len(samples),'repeats':args.repeats,
                'modes':MODES,'expected_predictions':len(pairs)*len(MODES)*args.repeats,
                'settings':{'model':base.lmstudio_model,'embedding_model':base.embedding_model,
                    'budget':base.prompt_token_budget,'cutoff':base.memory_min_similarity,
                    'recent_message_limit':base.working_memory_message_limit,'temperature':0.1,
                    'seeds':[42+i for i in range(args.repeats)],'max_output_tokens':128},
                'protocol':'Source dialogue and provided captions only. No QA references or predictions indexed. Direct production context-builder evaluation.',
                'storage':'Isolated real local MySQL; separate per-mode per-conversation namespaces. Graph and vector only enabled in their respective modes.',
                'hardware':{'platform':platform.platform(),'architecture':platform.machine()},
                'source_hashes':{str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'backend/services/chat_service.py',
                    ROOT/'backend/services/response_blueprint.py',ROOT/'response_blueprint.json',
                    ROOT/'memory_blueprint.json',ROOT/'backend/memory/session_memory.py',ROOT/'backend/database/chroma_repository.py',
                    ROOT/'backend/memory/semantic_chat.py',ROOT/'backend/memory/rolling_summary.py',
                    ROOT/'backend/memory/graph_memory.py',ROOT/'backend/utils/temporal_context.py',ROOT/'backend/utils/local_endpoints.py',ROOT/'backend/config.py',ROOT/'backend/main.py',ROOT/'backend/database/mysql_store.py',ROOT/'backend/database/mysql_repository.py',Path(__file__)]}}
            for key,setting in [('memory_bytes','hw.memsize'),('cpu','machdep.cpu.brand_string')]:
                try:manifest['hardware'][key]=subprocess.check_output(['sysctl','-n',setting],text=True).strip()
                except (OSError,subprocess.CalledProcessError):pass
            # Model inventory is local server metadata, not assumed quantisation.
            manifest['model_inventory']=models.json()
            try:
                inventory=http.get(base.lmstudio_base_url.replace('/v1','/api/v0')+'/models')
                if inventory.is_success:
                    manifest['runtime_model_metadata']=[{k:m.get(k) for k in ['id','state','max_context_length','loaded_context_length','quantization','arch']} for m in inventory.json().get('data',[]) if 'qwen' in m.get('id','')]
            except httpx.HTTPError:pass
            snapshot=out/'source_snapshot';snapshot.mkdir()
            for name,expected in manifest['source_hashes'].items():
                target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
                assert digest(target)==expected
            (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
        else:
            manifest=prior
            assert digest(data)==prior['dataset_sha256'] and digest(scorer_path)==prior['scorer_sha256']
            for name,expected in prior['source_hashes'].items():
                if name!=str(Path(__file__).relative_to(ROOT)) and digest(ROOT/name)!=expected:
                    raise RuntimeError('Source changed since interruption: '+name)
            with (out/'resume_events.jsonl').open('a') as handle:
                handle.write(json.dumps({'resumed_utc':stamp,'runner_sha256':digest(__file__),'note':'Source/configuration unchanged; completed predictions skipped'})+'\n')
        rows=[json.loads(line) for line in (out/'predictions.jsonl').read_text().splitlines()] if prior else []
        cleanup=json.loads((out/'cleanup.json').read_text()) if prior else []
        completed={(r['sample_id'],r['qa_index'],r['mode'],r['repeat']) for r in rows}
        print(f'Output: {out}\nQuestions: {len(pairs)}, predictions: {manifest["expected_predictions"]}',flush=True)
        for sample in samples:
            for mode in MODES:
                mode_questions=[(i,q) for source,i,q in pairs if source['sample_id']==sample['sample_id']]
                if all((sample['sample_id'],i,mode,r) in completed for i,q in mode_questions for r in range(args.repeats)):continue
                with tempfile.TemporaryDirectory(prefix=f'panel-{mode}-') as tmp:
                    settings=Settings(_env_file=None,chroma_path=Path(tmp),mysql_enabled=True,
                        graph_enabled=mode in {'graph','hybrid'},memory_configuration=mode,local_only=True,
                        lmstudio_base_url=base.lmstudio_base_url,lmstudio_model=base.lmstudio_model,
                        embedding_model=base.embedding_model,prompt_token_budget=base.prompt_token_budget,
                        working_memory_message_limit=base.working_memory_message_limit,
                        memory_min_similarity=base.memory_min_similarity)
                    with TestClient(create_app(settings)) as client:
                        service=client.app.state.chat_service;repo=service._repository
                        try:
                            started=time.perf_counter();history=seed_corpus(repo,sample)
                            if repo.semantic_memory:repo.semantic_memory.sync(history[0].user_id)
                            if getattr(repo,'graph_memory',None):repo.graph_memory.sync(history[0].user_id)
                            ingestion_ms=(time.perf_counter()-started)*1000
                            corpus_ids={m.id for m in history}
                            source_digest=hashlib.sha256(json.dumps([(m.id,m.content) for m in repo.list_user_messages(history[0].user_id)],ensure_ascii=False).encode()).hexdigest()
                            for index,qa in mode_questions:
                                for repeat in range(args.repeats):
                                    if (sample['sample_id'],index,mode,repeat) in completed:continue
                                    row={'sample_id':sample['sample_id'],'qa_index':index,'category':int(qa['category']),
                                        'mode':mode,'repeat':repeat,'seed':42+repeat,'question':qa['question'],
                                        'reference_answer':qa.get('answer',''),'gold_evidence':qa.get('evidence',[]),
                                        'corpus_ingestion_ms':ingestion_ms}
                                    try:
                                        query=Message(id=f'held-out-{index}',chat_id=history[0].chat_id,user_id=history[0].user_id,
                                            session_id='evaluation',role='user',content=qa['question'],timestamp=history[-1].timestamp+timedelta(days=1))
                                        instruction='\nAnswer the question about the supplied conversation with only the shortest factual answer. Preserve dates and names. If unsupported, answer: No information available.'
                                        allowance=service._prompt_token_budget
                                        service._prompt_token_budget=allowance-len(instruction.encode())
                                        started=time.perf_counter()
                                        try:messages,system=service._prepare_context(query)
                                        finally:service._prompt_token_budget=allowance
                                        row['context_build_ms']=(time.perf_counter()-started)*1000
                                        request={'model':base.lmstudio_model,'temperature':0.1,'seed':42+repeat,'max_tokens':128,
                                            'stream':False,'messages':[{'role':'system','content':system+instruction}]+[{'role':m.role,'content':m.content} for m in messages]}
                                        row['request_sha256']=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
                                        with (out/'requests.jsonl').open('a') as handle:
                                            handle.write(json.dumps({'sample_id':sample['sample_id'],'qa_index':index,
                                                'mode':mode,'repeat':repeat,'request':request})+'\n')
                                        started=time.perf_counter();response=http.post(base.lmstudio_base_url+'/chat/completions',json=request)
                                        response.raise_for_status();result=response.json()
                                        row['generation_ms']=(time.perf_counter()-started)*1000
                                        row['served_model']=result.get('model')
                                        row['prediction']=result['choices'][0]['message']['content'].strip()
                                        row['finish_reason']=result['choices'][0].get('finish_reason')
                                        row['actual_input_tokens']=result.get('usage',{}).get('prompt_tokens')
                                        row['actual_output_tokens']=result.get('usage',{}).get('completion_tokens')
                                        # Reference is used only HERE, after generation.
                                        scored=dict(qa,answer=qa.get('answer',''),prediction=row['prediction'])
                                        row['official_score']=float(scorer['eval_question_answering']([scored],eval_key='prediction')[0][0])
                                        row['trace']=query.memory_trace
                                        row['prompt_byte_allowance_used']=token_upper_bound(system+instruction)+sum(token_upper_bound(m.content) for m in messages)
                                        retained=repo.list_user_messages(history[0].user_id)
                                        row['corpus_unchanged']=({m.id for m in retained}==corpus_ids and hashlib.sha256(json.dumps([(m.id,m.content) for m in retained],ensure_ascii=False).encode()).hexdigest()==source_digest)
                                        if not row['corpus_unchanged']:raise RuntimeError('Evaluation modified source dialogue')
                                    except Exception as error:row['error']=f'{type(error).__name__}: {error}'
                                    rows.append(row)
                                    with (out/'predictions.jsonl').open('a') as handle:handle.write(json.dumps(row)+'\n')
                                    write_report(out,rows,manifest)
                                    print(f'{len(rows)}/{manifest["expected_predictions"]} {sample["sample_id"]} {mode} Q{index} trial{repeat+1}: '+str(row.get('official_score',row.get('error'))),flush=True)
                        finally:
                            try:
                                if getattr(repo,'graph_memory',None):repo.graph_memory.clear_namespace()
                                repo.sql_store.clear_namespace()
                                cleanup.append({'sample':sample['sample_id'],'mode':mode,'status':'removed'})
                            except Exception as error:
                                cleanup.append({'sample':sample['sample_id'],'mode':mode,'status':'failed','error':str(error)})
                            (out/'cleanup.json').write_text(json.dumps(cleanup,indent=2))
        write_report(out,rows,manifest)
        print('Completed:',out,flush=True)

if __name__=='__main__':main()
