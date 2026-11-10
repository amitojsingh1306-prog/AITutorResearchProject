"""Exercise the project's real local model adapters without saving a conversation."""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import sys,time
from types import SimpleNamespace
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('ANONYMIZED_TELEMETRY','False')
from backend.config import Settings
from backend.memory.semantic_chat import SemanticChatMemory
from backend.utils.local_endpoints import require_loopback


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chat',action='store_true',help='Also exercise the local Qwen generation adapter')
    args=parser.parse_args()
    settings=Settings();base=require_loopback(settings.lmstudio_base_url,'LM Studio').rstrip('/')
    marker='LM_LINK_CHECK_'+uuid4().hex[:8]
    text=f'{marker}: I am learning binary search in Python.'
    print('UTC:',datetime.now(timezone.utc).isoformat(),flush=True)
    print('Marker:',marker,flush=True)
    print('Calling: SemanticChatMemory.embed()',flush=True)
    print('Destination:',base+'/embeddings',flush=True)
    print('Model:',settings.embedding_model,flush=True)
    print('Input: search_query: '+text,flush=True)
    # embed() needs only these connection settings. Calling the real method
    # directly avoids constructing a Chroma collection or saving test messages.
    connection=SimpleNamespace(base_url=base,model=settings.embedding_model)
    started=time.perf_counter()
    vector=SemanticChatMemory.embed(connection,[text],query=True)[0]
    print('RECEIVED: validated embedding from the server',flush=True)
    print('Dimensions:',len(vector),flush=True)
    print('First 8 coordinates:',vector[:8],flush=True)
    print('Embedding round trip (ms):',round((time.perf_counter()-started)*1000,2),flush=True)
    if args.chat:
        from backend.llm.groq_client import GroqClient
        client=GroqClient(api_key='local',model=settings.lmstudio_model,base_url=base,
                          num_predict=16,temperature=0.1,timeout_seconds=60)
        print('\nCalling: GroqClient.generate_text() (historical adapter name; local URL)',flush=True)
        print('Destination:',base+'/chat/completions',flush=True)
        print('Model:',settings.lmstudio_model,flush=True)
        answer=client.generate_text(system_prompt='Follow the user instruction. Reply with only the requested text.',
             user_content=f'{marker}. Reply with exactly: LOCAL_QWEN_OK',temperature=0.1)
        print('RECEIVED QWEN REPLY:',answer,flush=True)
    print('\nMatch the marker in LM Studio Developer Logs. No chat or memory records were saved.',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(f'CONNECTION CHECK FAILED: {type(error).__name__}: {error}',file=sys.stderr)
        sys.exit(1)
