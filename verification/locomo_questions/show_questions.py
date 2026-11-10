"""Display the exact saved benchmark questions, answers and measurements."""
import argparse
import json
import statistics
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question',type=int,help='Display number from 1 to 49')
    parser.add_argument('--answers',action='store_true',help='Show each saved Qwen answer and timing')
    args=parser.parse_args()
    data=json.loads(Path(__file__).with_name('questions_and_results.json').read_text())
    if args.question is not None and not 1 <= args.question <= len(data['questions']):
        parser.error('Question number must be between 1 and 49.')
    print(f"SAVED BENCHMARK: {data['question_count']} questions, {data['prediction_count']} predictions")
    print('No new model requests. Category 5 score is abstention; other categories use answer F1.')
    for q in data['questions']:
        if args.question is not None and q['number'] != args.question:
            continue
        print(f"\n{q['number']:02d}. {q['question']}")
        print(f"SOURCE: {q['sample_id']} | QA index {q['qa_index']} | {q['category_name']}")
        print('REFERENCE:',q['reference_answer'] if q['category'] != 5 else '[unsupported question: abstention expected]')
        for mode in ('buffer','summary','vector','graph'):
            rows=[r for r in q['results'] if r['mode']==mode]
            avg=lambda key: statistics.mean(r[key] for r in rows)
            print(f"  {mode:7} mean score={avg('official_score'):.4f} request={avg('generation_ms'):.2f} ms context={avg('context_build_ms'):.2f} ms")
            if args.answers:
                for r in rows:
                    print(f"    Trial {r['repeat']+1}: {r['prediction']}")
                    print(f"      Score={r['official_score']:.6f}, request={r['generation_ms']:.2f} ms, context={r['context_build_ms']:.2f} ms")

if __name__=='__main__':
    main()
