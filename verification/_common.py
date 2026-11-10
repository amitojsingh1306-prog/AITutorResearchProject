"""Shared isolated fixtures; production behavior stays in backend modules."""
import os,sys,tempfile,time
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('ANONYMIZED_TELEMETRY','False')
from backend.config import Settings
from backend.memory.semantic_chat import SemanticChatMemory
from backend.models.chat import ChatSummary,Message
from backend.utils.local_endpoints import require_loopback

USER='verification-learner'
DOCUMENTS=[
 ('profile',"My name is Amitoj. I'm learning binary search in Python. I prefer short numbered explanations."),
 ('difficulty','When implementing binary search, I keep confusing low, high and mid.'),
 ('unrelated','My lunch was rice and vegetables.'),
]

def embedding_connection():
    settings=Settings()
    return settings,SimpleNamespace(base_url=require_loopback(settings.lmstudio_base_url).rstrip('/'),model=settings.embedding_model)

@contextmanager
def isolated_repository():
    from backend.database.chroma_repository import ChromaChatRepository
    with tempfile.TemporaryDirectory(prefix='tutor-verification-') as directory:
        repo=ChromaChatRepository(Path(directory));now=datetime.now(timezone.utc)
        repo.save_chat(ChatSummary(id='demo-chat',user_id=USER,session_id='demo-session',title='Verification only',created_at=now,updated_at=now))
        yield repo

@contextmanager
def semantic_demo():
    settings,connection=embedding_connection()
    with isolated_repository() as repo:
        memory=SemanticChatMemory(repo,connection.base_url,settings.embedding_model)
        repo.semantic_memory=memory
        now=datetime.now(timezone.utc)
        history=[]
        for index,(key,text) in enumerate(DOCUMENTS):
            message=Message(id=key,chat_id='demo-chat',session_id='demo-session',user_id=USER,role='user',content=text,timestamp=now+timedelta(microseconds=index))
            repo.save_message(message);history.append(message)
        # A save logs sync failures; explicit sync propagates any failure to this check.
        memory.sync(USER)
        yield repo,memory,history

def query_message(text='What do I find difficult when implementing binary search?'):
    return Message(id='query-not-saved',chat_id='demo-chat',session_id='demo-session',user_id=USER,role='user',content=text,timestamp=datetime.now(timezone.utc))

def check_main(function):
    try:
        function()
        print('\nPASS — this component check completed. Not a general accuracy score.',flush=True)
    except Exception as error:
        print(f'\nFAIL — {type(error).__name__}: {error}',file=sys.stderr,flush=True)
        sys.exit(1)
