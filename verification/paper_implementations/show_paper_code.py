"""Read-only research-to-production code viewer. No model requests or database writes."""
import argparse
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MAP=Path(__file__).with_name('paper_code_map.json')

def locate(spec):
    path=(ROOT/spec['file']).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Code path is outside the project.')
    source=path.read_text();lines=source.splitlines()
    if 'symbol' in spec:
        parts=spec['symbol'].split('.');nodes=ast.parse(source).body;found=None
        for part in parts:
            found=next((n for n in nodes if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==part),None)
            if found is None:raise ValueError(f"Missing production symbol: {spec['file']}::{spec['symbol']}")
            nodes=found.body
        return path,lines,found.lineno,found.end_lineno
    matches=[i+1 for i,line in enumerate(lines) if spec['anchor'] in line]
    if len(matches)!=1:raise ValueError(f"Expected one code anchor in {spec['file']}, found {len(matches)}")
    at=matches[0];radius=spec.get('radius',8)
    return path,lines,max(1,at-radius),min(len(lines),at+radius)

def main():
    items=json.loads(MAP.read_text())['items']
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paper',choices=[i['id'] for i in items],help='Show the actual code for one research connection')
    parser.add_argument('--full',action='store_true',help='Show complete functions instead of the first 55 lines')
    parser.add_argument('--check',action='store_true',help='Verify every linked file, function and demonstration script exists')
    args=parser.parse_args()
    if args.check:
        count=0
        for item in items:
            for spec in item['code']:locate(spec);count+=1
            for cmd in item['commands']:
                if not (ROOT/cmd.split()[0]).is_file():raise ValueError('Missing demonstration: '+cmd)
        print(f'PASS: {len(items)} research/engineering mappings and {count} production code locations exist.')
        print('This checks the guide links only; it does not run the models or certify model accuracy.')
        return
    print('RESEARCH IDEAS AND ACTUAL PROJECT CODE')
    print('This viewer reads production files directly. No copied substitute implementation runs.')
    if args.paper is None:
        for item in items:
            print(f"\n{item['id']:12} {item['title']}\n  {item['status']}")
        print('\nChoose: .venv/bin/python -B verification/paper_implementations/show_paper_code.py --paper rag')
        return
    item=next(i for i in items if i['id']==args.paper)
    print('\n'+item['title']+'\n'+item['status'])
    print('CONNECTION:',item['explain'])
    if item['source']:print('PAPER:',item['source'])
    for spec in item['code']:
        path,lines,start,end=locate(spec);stop=end if args.full else min(end,start+54)
        print(f"\nPRODUCTION FILE: {path}\nLINES: {start}-{end}")
        for n in range(start,stop+1):print(f'{n:4}: {lines[n-1]}')
        if stop<end:print(f'... {end-stop} more lines. Add --full to show the complete function.')
    print('\nDEMONSTRATION COMMANDS (run separately):')
    print('cd '+str(ROOT))
    for cmd in item['commands']:print('.venv/bin/python -B '+cmd)
    print('\nLIMIT:',item['limit'])

if __name__=='__main__':
    main()
