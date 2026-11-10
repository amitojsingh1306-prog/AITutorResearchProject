from datetime import datetime, timedelta, timezone
import json

from backend.database.chroma_repository import ChromaChatRepository
from backend.memory.graph_memory import extract_facts
from backend.memory.rolling_summary import RollingSummary
from backend.models.chat import ChatSummary, Message
from backend.services.chat_service import ChatService


def message(index, text, role='user'):
    return Message(id=f'm{index}', chat_id='chat', user_id='learner', session_id='session',
                   role=role, content=text, timestamp=datetime.now(timezone.utc)+timedelta(seconds=index))


def repository(tmp_path):
    repo=ChromaChatRepository(tmp_path)
    now=datetime.now(timezone.utc)
    repo.save_chat(ChatSummary(id='chat',user_id='learner',session_id='session',title='Test',created_at=now,updated_at=now))
    return repo


def test_rolling_summary_is_updated_persisted_bounded_and_used_with_recent_turns(tmp_path):
    repo=repository(tmp_path)
    history=[message(i,f'I am learning recursion lesson {i}.') for i in range(8)]
    for item in history: repo.save_message(item)
    current=message(9,'What did we discuss?');repo.save_message(current)
    engine=RollingSummary(repo,recent_turns=3,byte_budget=300)
    text,recent,trace=engine.context(current,history)
    assert text and len(text.encode())<=300
    assert [m.id for m in recent]==['m5','m6','m7']
    path=repo.session_memory._path('learner','chat')
    record=json.loads(path.read_text()); expiry=record['expires_at']
    assert record['rolling_summary']==text and trace['strategy']=='extractive'
    # Correction to a source invalidates cached summary instead of keeping stale text.
    history[4]=history[4].model_copy(update={'content':'I am now learning binary search.'})
    repo.save_message(history[4])
    changed,_,_=engine.context(current,history)
    assert 'binary search' in changed
    # Deriving the summary itself never touches the idle expiry.
    before=json.loads(path.read_text())['expires_at'];engine.context(current,history)
    assert json.loads(path.read_text())['expires_at']==before
    service=ChatService(repo,memory_configuration='summary',working_memory_limit=3)
    context,system=service._prepare_context(current)
    assert 'Earlier conversation summary' in system
    assert len(context)==4 and current.memory_trace['rolling_summary']['included_in_prompt']
    assert current.memory_trace['prompt_token_upper_bound']<=2800


def test_fact_extraction_uses_only_assertions_and_marks_corrections_and_resolved_difficulty():
    facts=extract_facts([
      message(0,'My name is Amitoj.'), message(1,"I'm learning binary search in Python."),
      message(2,'I keep confusing low, high and mid.'),
      message(3,'My name is AJ.'), message(4,'Your university is Invented College.','assistant'),
      message(5,'Which university do I attend?'), message(6,'I now understand binary search.'),
    ])
    active=[f for f in facts if f['active']]
    assert [f['value'] for f in active if f['kind']=='name']==['AJ']
    assert not any(f['kind']=='university' for f in facts)
    assert not any(f['kind']=='difficulty' for f in active)
    assert any(f['kind']=='completed' and f['topic']=='binary search' for f in active)
    assert all(f['message'].role=='user' for f in facts)


def test_buffer_configuration_does_not_sneak_in_graph_or_summary(tmp_path):
    repo=repository(tmp_path)
    for i in range(6): repo.save_message(message(i,'I prefer short numbered explanations.'))
    current=message(9,'Explain binary search.');repo.save_message(current)
    service=ChatService(repo,memory_configuration='buffer',working_memory_limit=2)
    selected,system=service._prepare_context(current)
    assert len(selected)==3
    assert current.memory_trace['rolling_summary']['status']=='disabled'
    assert current.memory_trace['graph_memory']['status']=='disabled'
    assert 'Earlier conversation summary' not in system


def test_institution_initials_are_not_truncated_at_internal_periods():
    facts=extract_facts([message(0,'My name is Amitoj. I attend S.R.M University.')])
    assert next(f['value'] for f in facts if f['kind']=='name')=='Amitoj'
    assert next(f['value'] for f in facts if f['kind']=='university')=='S.R.M University'
