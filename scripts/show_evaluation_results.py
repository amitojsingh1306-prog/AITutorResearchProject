"""Print verified LoCoMo results, category scores and an actual scoring example."""
import argparse,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
NAMES={1:'Multi-hop',2:'Temporal',3:'Open-domain',4:'Single-hop',5:'Abstention'}

def table(headers,rows):
    rows=[[str(v) for v in row] for row in rows]
    widths=[max(len(str(h)),*(len(row[i]) for row in rows)) for i,h in enumerate(headers)]
    print('  '.join(str(h).ljust(widths[i]) for i,h in enumerate(headers)))
    print('  '.join('-'*w for w in widths))
    for row in rows:print('  '.join(v.ljust(widths[i]) for i,v in enumerate(row)))

def number(v,digits=4):return 'n/a' if v is None else f'{v:.{digits}f}'

def latest():
    choices=[]
    for path in (ROOT/'benchmark_outputs/panel').glob('*/audit.json'):
        try:
            audit=json.loads(path.read_text());manifest=json.loads((path.parent/'manifest.json').read_text())
            summary=json.loads((path.parent/'summary.json').read_text())
            if audit.get('passed') and summary.get('completed'):
                choices.append((manifest['created_utc'],path.parent))
        except (OSError,ValueError,KeyError):pass
    if not choices:raise SystemExit('No completed, independently verified run is available yet.')
    return max(choices)[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,help='Run folder; defaults to latest completed independently audited run')
    parser.add_argument('--answers',action='store_true',help='Also print every saved question, prediction and reference')
    args=parser.parse_args();out=(args.run or latest()).resolve()
    manifest=json.loads((out/'manifest.json').read_text());summary=json.loads((out/'summary.json').read_text())
    audit=json.loads((out/'audit.json').read_text())
    if not summary['completed'] or not audit['passed']:
        raise SystemExit('This run is incomplete or failed its audit. Do not present it as verified.')
    rows=[json.loads(line) for line in (out/'predictions.jsonl').read_text().splitlines()]
    print('\nVERIFIED LOCAL LoCoMo EVALUATION\n')
    print('Source: https://github.com/snap-research/locomo')
    print(f"Scope: {manifest['unique_questions']} unique selected questions across {manifest['conversations']} conversations")
    print(f"Trials: {manifest['repeats']} per question and mode; saved predictions: {len(rows)}")
    print(f"Models: {manifest['settings']['model']} / {manifest['settings']['embedding_model']}")
    print(f"Input allowance: {manifest['settings']['budget']} conservative UTF-8 byte units, not actual tokenizer tokens")
    print(f"Similarity threshold: {manifest['settings']['cutoff']}; temperature: {manifest['settings']['temperature']}")
    print(f"Audit: PASS; rescored {audit['rescored_predictions']}; findings: {len(audit['findings'])}")
    print('\nOVERALL\n')
    table(['Memory','Answer F1 (1-4)','Abstention (5)','Errors','Context ms','Generation ms','Input tokens'],[
        [mode,number(r['mean_answer_f1_categories_1_4']),number(r['abstention_phrase_score_category_5']),r['errors'],
         number(r['mean_context_build_ms'],2),number(r['mean_generation_request_ms'],2),number(r['mean_actual_input_tokens'],1)]
        for mode,r in summary['results'].items()])
    print('\nBY CATEGORY\n')
    table(['Memory',*[NAMES[c] for c in NAMES]],[
        [mode,*[number(r['categories'][str(c)]['score']) for c in NAMES]] for mode,r in summary['results'].items()])
    print('\nRETRIEVAL DIAGNOSTICS\n')
    table(['Memory','Evidence-ID precision','Evidence-ID recall','Output cap reached'],[
        [mode,number(audit['evidence_diagnostics'][mode]['mean_evidence_id_precision']),
         number(audit['evidence_diagnostics'][mode]['mean_evidence_id_recall']),
         sum(r.get('finish_reason')=='length' for r in rows if r['mode']==mode)] for mode in manifest['modes']])
    print('\nINTERPRETATION\n')
    for warning in audit.get('interpretation_warnings',[]):print('WARNING:',warning)
    if audit.get('memory_path_participation'):
        print('Requests with added evidence (summary / vector / graph):')
        for mode,item in audit['memory_path_participation'].items():
            print(f"  {mode}: {item['summary_in_prompt']} / {item['vector_evidence_added']} / {item['graph_evidence_added']} of {item['completed_requests']}")
    print('Answer F1 measures normalized, stemmed wording overlap with withheld references. It is not factual accuracy probability.')
    print('Category 5 uses the upstream abstention phrase rule. It is separate from answer F1 and memory retrieval recall.')
    print('Evidence-ID recall checks whether annotated supporting message IDs reached the prompt; excerpts may omit key text.')
    print('Context timing covers context construction. Generation timing covers the local HTTP generation request. Corpus ingestion is separate.')
    print('Three trials reuse the same questions. This selected subset does not establish full-dataset or paper-level performance.')
    best=max(summary['results'],key=lambda m:summary['results'][m]['mean_answer_f1_categories_1_4'] or 0)
    print(f"Highest mean answer F1 in this run: {best} ({number(summary['results'][best]['mean_answer_f1_categories_1_4'])}).")
    print('A valid experiment can still show weak model performance. Inspect failures before calling the answers good.')
    print('\nSAVED EXAMPLES\n')
    examples=[]
    for c in NAMES:
        candidates=[r for r in rows if r['category']==c and r['mode']==best and r['repeat']==0 and 'official_score' in r]
        if candidates:
            examples.append(min(candidates,key=lambda r:r['official_score']))
            strongest=max(candidates,key=lambda r:r['official_score'])
            if strongest['official_score']>examples[-1]['official_score']:examples.append(strongest)
    for r in examples:
        print(f"{NAMES[r['category']]} | {r['sample_id']} Q{r['qa_index']} | {r['mode']} | score {r['official_score']:.4f}")
        print('Question:',r['question']);print('Reference:',r['reference_answer']);print('Qwen:',r['prediction']);print()
    explain=next((r for r in rows if r['category'] in [2,3,4] and 0<r.get('official_score',0)<1),None)
    if explain:
        from collections import Counter
        from scripts.run_official_locomo import load_official_scorer
        scorer=load_official_scorer(ROOT/'benchmark_data/locomo/upstream_evaluation.py')
        target=str(explain['reference_answer'])
        if explain['category']==3:target=target.split(';')[0].strip()
        tokens=lambda value:[scorer['ps'].stem(w) for w in scorer['normalize_answer'](value).split()]
        p,g=tokens(explain['prediction']),tokens(target);k=sum((Counter(p)&Counter(g)).values())
        precision=k/len(p) if p else 0;recall=k/len(g) if g else 0
        print('WORKED SCORE\n')
        print('Question:',explain['question']);print('Qwen:',explain['prediction']);print('Reference:',target)
        print(f'Matching normalized stemmed tokens: {k}; predicted: {len(p)}; reference: {len(g)}')
        print(f'Precision = {k}/{len(p)} = {precision:.4f}; recall = {k}/{len(g)} = {recall:.4f}')
        print(f"F1 = 2*precision*recall/(precision+recall) = {explain['official_score']:.4f}")
        print('Overlap credit does not establish that dates, entities or every factual claim are correct.\n')
    if args.answers:
        print('\nALL SAVED PREDICTIONS\n')
        for r in rows:
            print(f"{r['sample_id']} Q{r['qa_index']} {r['mode']} trial {r['repeat']+1}, category {r['category']}, score {r.get('official_score','ERROR')}")
            print('Question:',r['question']);print('Reference:',r['reference_answer']);print('Qwen:',r.get('prediction',r.get('error')));print()
    graph_report=ROOT/'benchmark_outputs/graph_auto_update_verification.json'
    if graph_report.exists():
        graph=json.loads(graph_report.read_text())
        print('\nDATABASE INTEGRATION CHECK:', 'PASS' if graph['passed'] else 'FAIL')
        for name,passed in graph['checks'].items():print('  ',name,':', 'PASS' if passed else 'FAIL')
    live_report=ROOT/'benchmark_outputs/live_tutor_route_verification.json'
    if live_report.exists():
        live=json.loads(live_report.read_text())
        print('\nLIVE CHAT-ROUTE CHECK:', 'PASS' if live['passed'] else 'FAIL')
        for name,passed in live['checks'].items():print('  ',name,':', 'PASS' if passed else 'FAIL')
        print('Saved live questions and answers:',live_report)
    failure=ROOT/'benchmark_outputs/live_tutor_nonstream_failure.json'
    if failure.exists():print('KNOWN LIVE LIMITATION: non-streaming route timed out at 60 s; see',failure)
    print('Explanation:',out/'evaluation_explained.md')
    print('Reports:',out/'report.md');print('All answers and traces:',out/'predictions.jsonl')
    print('Exact model requests:',out/'requests.jsonl');print('CSV:',out/'comparison.csv');print('Audit:',out/'audit.json')
    return 0

if __name__=='__main__':raise SystemExit(main())
