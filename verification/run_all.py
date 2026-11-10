"""Run focused component demonstrations; databases are opt-in."""
from _common import ROOT
import argparse,subprocess,sys

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-databases',action='store_true',help='Also check real local MySQL and Neo4j')
    args=parser.parse_args()
    names=['verify_nomic_embeds','verify_chroma_storage','verify_cosine','verify_context','verify_rolling_summary','verify_blueprint','verify_qwen']
    if args.include_databases:names+=['verify_mysql','verify_neo4j']
    failed=[]
    for name in names:
        print('\n'+'='*65+'\n'+name+'\n'+'='*65,flush=True)
        result=subprocess.run([sys.executable,'-B',str(ROOT/'verification'/(name+'.py'))],cwd=ROOT)
        if result.returncode:failed.append(name)
    print('\nCOMPONENT CHECKS:',len(names)-len(failed),'passed;',len(failed),'failed.',flush=True)
    if failed:print('FAILURES:',', '.join(failed))
    print('These are focused checks, not a LoCoMo score or a guarantee of general answer correctness.')
    sys.exit(bool(failed))
