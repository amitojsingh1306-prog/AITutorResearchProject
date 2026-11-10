"""Start this checkout's backend and frontend; Ctrl+C stops both."""

import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from backend.config import Settings
    python = ROOT / '.venv/bin/python'
    npm = shutil.which('npm')
    if not python.is_file() or not npm or not (ROOT / 'frontend/node_modules').is_dir():
        raise SystemExit('Python environment or frontend dependencies are missing.')
    for port in (8000, 5173):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                raise SystemExit(f'Port {port} is already in use. Stop the existing server first.')
    env = dict(os.environ, CHATBOT_LMSTUDIO_BASE_URL='http://127.0.0.1:1234/v1',
               CHATBOT_GROQ_API_KEY='', GROQ_API_KEY='', PYTHONDONTWRITEBYTECODE='1',
               VITE_API_URL='http://127.0.0.1:8000', ANONYMIZED_TELEMETRY='False',
               CHROMA_PRODUCT_TELEMETRY_IMPL='backend.chroma_noop_telemetry.NoopProductTelemetry')
    if Settings().mysql_enabled:
        subprocess.run([str(python), str(ROOT / 'scripts/mysql_server.py'), 'start'], check=True)
    if Settings().graph_enabled:
        subprocess.run([str(python), str(ROOT / 'scripts/graph_server.py'), 'start'], check=True)
    children = []
    try:
        children.append(subprocess.Popen(
            [str(python), '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000'],
            cwd=ROOT, env=env, start_new_session=True))
        children.append(subprocess.Popen(
            [npm, 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173', '--strictPort'],
            cwd=ROOT / 'frontend', env=env, start_new_session=True))
        print(f'Project: {ROOT}\nChat: http://127.0.0.1:5173\nCtrl+C stops both servers.', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        raise SystemExit('A server stopped; see its error above.')
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


if __name__ == '__main__':
    main()
