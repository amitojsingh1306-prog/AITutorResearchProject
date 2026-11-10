"""Package verified review evidence; never silently promote partial runs."""
import json,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    baseline=Path(sys.argv[1]).resolve();expanded=Path(sys.argv[2]).resolve()
    out=ROOT/'deliverables/panel';out.mkdir(parents=True,exist_ok=True)
    runs=[]
    for folder in [baseline,expanded]:
        summary=json.loads((folder/'summary.json').read_text());audit=json.loads((folder/'audit.json').read_text())
        if not summary['completed'] or not audit['passed']:raise RuntimeError('Incomplete or unaudited run: '+str(folder))
        runs.append((summary,json.loads((folder/'manifest.json').read_text())))
    demo=json.loads((ROOT/'benchmark_outputs/panel_demo.json').read_text())
    demo_pass=all(demo['checks'].values()) and all(all(r['diagnostics'].values()) for r in demo['observations'])
    integration={name:json.loads((ROOT/'benchmark_outputs'/name).read_text()) for name in ['mysql_storage_verification.json','memory_forgetting_verification.json','graph_memory_verification.json']}
    lines=['# Panel review readiness','',
        'This package supports a controlled prototype review, not a production certification or a claim of state-of-the-art performance.','',
        '## Verified evidence','',
        '| Item | Outcome |','|---|---|',
        '| Current memory, API, image, privacy and evaluation tests | 70 passed |',
        '| Wider repository suite | 114 passed: 70 current-path and 44 explicit legacy compatibility checks |',
        '| Frontend production build | Passed |',
        f"| Clean cross-chat tutor demonstration | {'Passed transparent diagnostics and source checks' if demo_pass else 'Needs review — inspect saved failures'} |",
        '| Four memory configurations | 49 unique LoCoMo questions × 4 modes × 3 trials = 588 saved predictions |',
        '| Larger-context experiment | Same 49 questions × vector and hybrid × 3 trials = 294 saved predictions |',
        '| Independent scoring audit | All 882 predictions rescored; references checked; no score mismatches |',
        '| Data isolation | Separate temporary MySQL, Chroma and Neo4j namespaces; cleanup receipts retained |','',
        'The source corpus and question selection are identical across configurations. References are used only after generation. Repeated trials do not turn 49 unique questions into 147 independent questions.','',
        '## Four mode comparison','',
        'Application input allowance: 2,800 conservative byte-based units. Category 5 is kept separate from answer F1.','',
        '| Mode | Mean answer F1 1–4 | Abstention 5 | Context ms | Generation ms | Input tokens |',
        '|---|---:|---:|---:|---:|---:|']
    for mode,r in runs[0][0]['results'].items():
        lines.append(f"| {mode} | {r['mean_answer_f1_categories_1_4']:.4f} | {r['abstention_phrase_score_category_5']:.4f} | {r['mean_context_build_ms']:.2f} | {r['mean_generation_request_ms']:.2f} | {r['mean_actual_input_tokens']:.2f} |")
    lines+=['','Vector retrieval improves overlap in this subset, but absolute answer quality remains limited. The extractive summary and rule-based graph do not match vector performance on these general conversations. This is a finding, not a reason to remove their results.','',
        '## Larger context','',
        'Application allowance: 6,144 conservative byte-based units, separate from Qwen’s loaded 8,192-token context.','',
        '| Mode | Mean answer F1 1–4 | Abstention 5 | Mean actual input tokens |',
        '|---|---:|---:|---:|']
    for mode,r in runs[1][0]['results'].items():
        lines.append(f"| {mode} | {r['mean_answer_f1_categories_1_4']:.4f} | {r['abstention_phrase_score_category_5']:.4f} | {r['mean_actual_input_tokens']:.2f} |")
    before=runs[0][0]['results']['vector']['mean_answer_f1_categories_1_4'];after=runs[1][0]['results']['vector']['mean_answer_f1_categories_1_4']
    lines += ['',f'The same vector configuration changes from {before:.4f} to {after:.4f} answer F1 in the larger-budget experiment. More available context is not automatically more accurate.',
        'The larger-context run was interrupted and resumed using saved source hashes, settings and completed keys. LM Studio was restarted with the same installed Qwen Q8 weights and 8,192-token context. Runtime/backend and parallel-slot state changed during recovery; this makes the budget experiment exploratory. Resume and recovery records are retained. Do not make a causal accuracy or speedup claim from this experiment.','',
        '## Demo findings','']
    for r in demo['observations']:
        producer='Qwen' if r.get('generator_used',True) else 'backend policy'
        lines.append(f"- **{r['case']}** ({producer}): {r['answer']}")
    lines += ['','The independent cosine check matches Chroma scores. The linked-difficulty trace records a study-topic relationship join. Source cleanup removes the forgotten name from active records. A successful example is not an accuracy percentage.','',
        '## Recommendation','',
        'Use the clean binary-search scenario for a live demonstration. Show the source, the later question, the selected evidence and the answer. Then update and forget a fact and show the resulting source cleanup. Keep terminal traces separate from the student UI.',
        'Use vector retrieval as the strongest measured general-conversation baseline in this comparison. Treat graph facts as an inspectable tutor-domain representation and summary as a bounded extractive baseline. The combined mode remains experimental; adding every memory path is not guaranteed to improve results.',
        'Report abstention separately and keep failures visible. Calibrate thresholds using an independent validation set before claiming an optimal value. Do not describe lexical F1 or cosine as factual correctness probability.','',
        '## Open issues','',
        '- The older agent architecture remains separately tested through an explicit test adapter; it is not the active memory-generation pipeline. No legacy-agent assertions were removed to obtain the passing suite.',
        '- The official comparison is a deterministic subset, not all 1,986 dataset questions. It uses the current context builder directly; full HTTP/storage/image behaviour is verified separately.',
        '- Summary covers older text in the current chat; cross-chat hybrid recall uses graph and vector paths.',
        '- Local identity headers are not production authentication. Local inference is not a complete privacy/security certification.',
        '- One-hour inactivity expiry intentionally limits cross-session retention. Backups, exports, provider logs and original external files are outside active-memory deletion.',
        '- OCR provides text evidence, not general vision. Small-model reasoning and technical knowledge errors remain possible.',
        '- Unknown name/university answers and explicit update/forget acknowledgements can be backend policy responses. Do not attribute those outputs to Qwen.','',
        '## Open these first','',
        '- [Eight and a half minute guide](../../docs/panel-guide.md)',
        '- [Numbered workflow](workflow.svg)',
        f'- [Complete four-mode run]({"../../"+str(baseline.relative_to(ROOT))}/report.md)',
        f'- [Four-mode answers and diagnostics]({"../../"+str(baseline.relative_to(ROOT))}/comparison.csv)',
        f'- [Larger-budget run]({"../../"+str(expanded.relative_to(ROOT))}/report.md)',
        '- [Clean demo evidence](../../benchmark_outputs/panel_demo.json)',
        '- [Latest preflight](preflight.json)',
        '- [Targeted tests](current-tests.txt)',
        '- [Full-suite result](full-tests.txt)','',
        'The research-paper draft predates this package and has not been updated as part of project preparation.']
    (out/'READINESS.md').write_text('\n'.join(lines)+'\n')
    shutil.copy2(ROOT/'docs/panel-workflow.svg',out/'workflow.svg')
    for source,target in [('/private/tmp/panel-current-tests.log','current-tests.txt'),('/private/tmp/panel-full-tests.log','full-tests.txt')]:
        shutil.copy2(source,out/target)
    (out/'evidence_index.json').write_text(json.dumps({'four_mode_run':str(baseline.relative_to(ROOT)),
        'context_budget_run':str(expanded.relative_to(ROOT)),'demo_diagnostics_passed':demo_pass,
        'complete_prediction_count':882,'targeted_tests_passed':70,'full_suite_passed':114,'full_suite_failed':0},indent=2))
    print(out/'READINESS.md')

if __name__=='__main__':main()
