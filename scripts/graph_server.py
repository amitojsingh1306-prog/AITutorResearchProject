"""Start/status/stop the project's own local Neo4j Community server."""
import argparse
import os
from pathlib import Path
import subprocess
import socket
import time

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['start','status','stop'],default='status',nargs='?')
    args=parser.parse_args()
    server=ROOT/'.local/neo4j-community-2026.10.1/bin/neo4j'
    if not server.is_file(): raise SystemExit('Local Neo4j is not installed; see docs/graph-memory.md.')
    env=dict(os.environ,JAVA_HOME='/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home')
    action = args.action
    if action == 'start' and subprocess.run([str(server),'status'],env=env,capture_output=True).returncode == 0:
        print('Project Neo4j is already running.')
    else:
        result = subprocess.call([str(server),action],env=env)
        if result: raise SystemExit(result)
    if action == 'start':
        for _ in range(45):
            try:
                with socket.create_connection(('127.0.0.1',7687),timeout=1): break
            except OSError: time.sleep(1)
        else: raise SystemExit('Neo4j has not become ready; check its local logs.')
