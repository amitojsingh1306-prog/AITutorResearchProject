"""Independently re-score saved predictions and export source-evidence diagnostics."""
import sys,json,csv,contextlib,io,statistics,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.run_official_locomo import load_official_scorer,conversation_messages,evidence_metrics
from backend.models.chat import Message


def main():
    out=Path(sys.argv[1]).resolve()
    manifest=json.loads((out/'manifest.json').read_text())
    rows=[json.loads(line) for line in (out/'predictions.jsonl').read_text().splitlines()]
    data={s['sample_id']:s for s in json.loads((ROOT/'benchmark_data/locomo/locomo10.json').read_text())}
    full={sample:sum(len(m.content.encode()) for m in conversation_messages(data[sample],Message)) for sample in data}
    scorer=load_official_scorer(ROOT/'benchmark_data/locomo/upstream_evaluation.py')
    errors=[];exports=[];seen=set()
    for name,key in [('locomo10.json','dataset_sha256'),('upstream_evaluation.py','scorer_sha256')]:
        if hashlib.sha256((ROOT/'benchmark_data/locomo'/name).read_bytes()).hexdigest()!=manifest[key]:
            errors.append({'input_hash_mismatch':name})
    for name,expected_hash in manifest.get('source_hashes',{}).items():
        snapshot=out/'source_snapshot'/name
        if snapshot.exists() and hashlib.sha256(snapshot.read_bytes()).hexdigest()!=expected_hash:
            errors.append({'snapshot_hash_mismatch':name})
    requests={}
    if (out/'requests.jsonl').exists():
        for line in (out/'requests.jsonl').read_text().splitlines():
            item=json.loads(line);key=(item['sample_id'],item['qa_index'],item['mode'],item['repeat'])
            if key in requests:errors.append({'duplicate_request':key})
            requests[key]=item['request']
    for row in rows:
        key=(row['sample_id'],row['qa_index'],row['mode'],row['repeat'])
        if key in seen:errors.append({'duplicate_prediction':key})
        seen.add(key)
        qa=data[row['sample_id']]['qa'][row['qa_index']]
        if row['question']!=qa['question'] or row['reference_answer']!=qa.get('answer',''):errors.append({'reference_mismatch':key})
        if 'error' in row or 'official_score' not in row:
            errors.append({'request_or_scoring_error':key,'detail':row.get('error','Missing score')})
            continue
        if requests:
            request=requests.get(key)
            if request is None or hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()!=row['request_sha256']:
                errors.append({'request_hash_mismatch':key})
            elif not request['messages'][-1]['content'].endswith(qa['question']):
                errors.append({'question_missing_from_prompt':key})
            if row.get('corpus_unchanged') is not True:errors.append({'source_corpus_changed':key})
        with contextlib.redirect_stdout(io.StringIO()):
            score=float(scorer['eval_question_answering']([dict(qa,answer=qa.get('answer',''),prediction=row['prediction'])],eval_key='prediction')[0][0])
        if abs(score-row['official_score'])>1e-10:errors.append({'score_mismatch':key})
        trace=row.get('trace',{})
        selected=set(trace.get('history_message_ids',[]))|set(trace.get('conversation_outline_message_ids',[]))|set(trace.get('graph_source_message_ids',[]))
        summary=trace.get('rolling_summary',{})
        if summary.get('included_in_prompt'):selected.update(summary.get('source_message_ids',[]))
        selected.update(item['id'] for item in trace.get('retrieved_memories',[]) if item.get('included_in_prompt'))
        corpus_ids={m.id for m in conversation_messages(data[row['sample_id']],Message)}
        if selected-corpus_ids:errors.append({'unknown_source_ids':key,'ids':sorted(selected-corpus_ids)})
        metrics=evidence_metrics([item.split('::',1)[-1] for item in selected],qa.get('evidence',[]))
        exports.append({'sample_id':row['sample_id'],'qa_index':row['qa_index'],'category':row['category'],
            'mode':row['mode'],'repeat':row['repeat'],'answer_score':score,'prediction':row['prediction'],
            'evidence_id_precision':metrics['precision'],'evidence_id_recall':metrics['recall'],
            'selected_source_ids':';'.join(sorted(selected)),'generation_request_ms':row['generation_ms'],
            'context_build_ms':row['context_build_ms'],'actual_input_tokens':row.get('actual_input_tokens'),
            'prompt_byte_bound':row.get('prompt_byte_allowance_used'),
            'full_raw_source_bytes':full[row['sample_id']]})
    expected={(q['sample_id'],q['qa_index'],mode,r) for q in manifest['selected_questions'] for mode in manifest['modes'] for r in range(manifest['repeats'])}
    if seen!=expected:errors.append({'missing':len(expected-seen),'unexpected':len(seen-expected)})
    cleanup=json.loads((out/'cleanup.json').read_text())
    if any(item['status']!='removed' for item in cleanup):errors.append({'cleanup':'incomplete'})
    expected_cleanup={(q['sample_id'],mode) for q in manifest['selected_questions'] for mode in manifest['modes']}
    actual_cleanup={(item['sample'],item['mode']) for item in cleanup if item['status']=='removed'}
    if actual_cleanup!=expected_cleanup:errors.append({'cleanup_coverage_mismatch':True})
    per_mode={};participation={};warnings=[]
    for mode in manifest['modes']:
        selected=[r for r in exports if r['mode']==mode]
        avg=lambda k:statistics.mean(r[k] for r in selected if isinstance(r[k],(int,float))) if any(isinstance(r[k],(int,float)) for r in selected) else None
        per_mode[mode]={'mean_evidence_id_precision':avg('evidence_id_precision'),
            'mean_evidence_id_recall':avg('evidence_id_recall'),
            'mean_prompt_byte_bound':avg('prompt_byte_bound'),'mean_full_raw_source_bytes':avg('full_raw_source_bytes')}
        original=[r for r in rows if r['mode']==mode and 'official_score' in r]
        participation[mode]={
            'summary_in_prompt':sum(bool(r.get('trace',{}).get('rolling_summary',{}).get('included_in_prompt')) for r in original),
            'vector_evidence_added':sum(any(item.get('included_in_prompt') for item in r.get('trace',{}).get('retrieved_memories',[])) for r in original),
            'graph_evidence_added':sum(any(item.get('included_in_prompt') for item in r.get('trace',{}).get('graph_memory',{}).get('facts',[])) for r in original),
            'completed_requests':len(original)}
        if mode=='summary' and not participation[mode]['summary_in_prompt']:
            warnings.append('Summary mode supplied no summary evidence at this input allowance. Do not interpret it as a test of effective summary augmentation.')
    report={'passed':not errors,'expected_predictions':len(expected),'saved_predictions':len(rows),
        'rescored_predictions':len(exports),'findings':errors,'evidence_diagnostics':per_mode,
        'memory_path_participation':participation,'interpretation_warnings':warnings,
        'note':'Evidence-ID overlap is not answer correctness; selected excerpts may omit source words. Byte bound and raw history exclude comparable tokenization, so no token-savings percentage is claimed.'}
    (out/'audit.json').write_text(json.dumps(report,indent=2))
    with (out/'comparison.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(exports[0]) if exports else ['sample_id'])
        writer.writeheader();writer.writerows(exports)
    print(json.dumps(report,indent=2));return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
