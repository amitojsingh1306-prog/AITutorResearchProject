"""Rescore a completed benchmark; this does not generate new model answers."""
from _common import ROOT
import runpy,sys

if __name__=='__main__':
    if len(sys.argv)==1:
        sys.path.insert(0,str(ROOT/'scripts'))
        from show_evaluation_results import latest
        sys.argv.append(str(latest()))
    runpy.run_path(str(ROOT/'scripts/audit_panel_results.py'),run_name='__main__')
