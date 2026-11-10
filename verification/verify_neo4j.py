"""Reuse the existing actual Neo4j/MySQL automatic-update integration check."""
from _common import ROOT
import runpy

if __name__=='__main__':
    print('Delegating to scripts/verify_graph_updates.py. Requires local Neo4j AND MySQL.',flush=True)
    print('Checks automatic sources/facts, correction and forgetting; isolated namespace only.',flush=True)
    runpy.run_path(str(ROOT/'scripts/verify_graph_updates.py'),run_name='__main__')
