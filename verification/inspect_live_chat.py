"""Read actual chatbot traces; defaults to the frontend's local-user identity."""
from _common import ROOT
import runpy,sys

if __name__=='__main__':
    if '--user' not in sys.argv and not any(arg.startswith('--user=') for arg in sys.argv):sys.argv.extend(['--user','local-user'])
    runpy.run_path(str(ROOT/'scripts/inspect_memory.py'),run_name='__main__')
