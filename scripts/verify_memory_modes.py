"""Small same-input memory-mode smoke comparison, not official LoCoMo results."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,timedelta,timezone
import json,tempfile,time
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.config import Settings
from backend.models.chat import Message

ROOT=Path(__file__).resolve().parents[1]

def main():
    results=[]
    for mode in ('buffer','summary','vector','graph'):
        with tempfile.TemporaryDirectory(prefix=f'tutor-{mode}-proof-') as tmp:
            settings=Settings(_env_file=None,chroma_path=Path(tmp),graph_enabled=mode=='graph',memory_configuration=mode)
            with TestClient(create_app(settings)) as client:
                repo=client.app.state.chat_service._repository
                graph=getattr(repo,'graph_memory',None)
                try:
                    headers={'X-User-Id':'same-input-proof'}
                    chat=client.post('/chat/create',headers=headers,json={}).json()
                    contents=["My name is Amitoj. I'm learning binary search in Python. I prefer short numbered explanations."]
                    contents += [f'Practice checkpoint {i}: please keep this exercise for later.' for i in range(12)]
                    for i,text in enumerate(contents):
                        repo.save_message(Message(id=f'source-{i}',chat_id=chat['id'],user_id=headers['X-User-Id'],
                            session_id=chat['session_id'],role='user',content=text,
                            timestamp=datetime.now(timezone.utc)-timedelta(minutes=20-i)))
                    started=time.perf_counter()
                    response=client.post(f"/chat/{chat['id']}/message",headers=headers,
                        json={'content':"What did I tell you about my name, what I'm learning, and how I prefer explanations?"})
                    assert response.status_code==201,response.text
                    reply=response.json()['assistant_message'];text=reply['content'].lower()
                    checks={'name':'amitoj' in text,'topic':'binary search' in text,
                            'preference':'short' in text and ('number' in text or 'steps' in text)}
                    results.append({'mode':mode,'answer':reply['content'],'term_presence_checks':checks,
                                    'request_ms':round((time.perf_counter()-started)*1000,2),
                                    'trace':reply['memory_trace']})
                    print(mode,json.dumps(checks),flush=True)
                finally:
                    if graph:graph.clear_namespace()
    report={'scope':'One custom same-input smoke question; not LoCoMo or general accuracy.',
            'scoring_note':'Term presence is a diagnostic, not semantic correctness scoring. Inspect the saved answers.',
            'summary_strategy':'extractive','results':results}
    path=ROOT/'benchmark_outputs/memory_modes_smoke.json'
    path.write_text(json.dumps(report,indent=2));print('Report:',path)

if __name__=='__main__':main()
