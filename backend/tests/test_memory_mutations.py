from datetime import datetime,timezone
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.models.chat import Message


class Tutor:
    def __init__(self):self.prompts=[]
    def generate_reply(self,messages,system_prompt=None):
        text='\n'.join([system_prompt or '',*[m.content for m in messages]])
        self.prompts.append(text)
        return 'Your name is AJ.' if 'My name is AJ' in text else 'I do not have your name saved.'
    def stream_reply(self,messages,system_prompt=None):yield self.generate_reply(messages,system_prompt)


def prepare(client):
    service=client.app.state.chat_service;repo=service._repository
    repo.semantic_memory=None;service._semantic_memory=None
    tutor=Tutor();service._llm_client=tutor
    headers={'X-User-Id':'learner-A'}
    chat=client.post('/chat/create',headers=headers,json={}).json()
    now=datetime.now(timezone.utc)
    source=Message(id='source',chat_id=chat['id'],user_id='learner-A',session_id=chat['session_id'],
        role='user',content="My name is Amitoj. I'm learning binary search in Python.",timestamp=now)
    repo.save_message(source)
    repo.save_message(source.model_copy(update={'id':'echo','role':'assistant','content':'Amitoj is learning binary search.'}))
    return service,repo,tutor,headers,chat,source


def test_chat_forget_physically_redacts_fact_preserves_other_facts_and_does_not_echo_it(tmp_path):
    with TestClient(create_app(Settings(_env_file=None,chroma_path=tmp_path))) as client:
        service,repo,tutor,headers,chat,source=prepare(client)
        url='/chat/'+chat['id']
        response=client.post(url+'/message/stream',headers=headers,json={'content':'Please forget my name.'})
        assert 'event: done' in response.text
        assert 'Amitoj' not in response.text and not tutor.prompts
        data=client.get(url,headers=headers).json()
        assert 'Amitoj' not in json.dumps(data)
        assert any('binary search' in m['content'] for m in data['messages'])
        assert not list(repo.mutations.directory.glob('operation-*.json'))
        response=client.post(url+'/message',headers=headers,json={'content':'What is my name?'})
        assert response.status_code==201 and response.json()['assistant_message']['content']=="I don't have your name saved."
        assert not tutor.prompts  # Missing identity is answered by the source guard.
        assert response.json()['assistant_message']['memory_trace']['generation_used'] is False


def test_update_delete_routes_enforce_ownership_and_invalidate_replies(tmp_path):
    with TestClient(create_app(Settings(_env_file=None,chroma_path=tmp_path))) as client:
        service,repo,tutor,headers,chat,source=prepare(client)
        url='/chat/'+chat['id']
        assert client.patch(url+'/messages/source',headers={'X-User-Id':'learner-B'},json={'content':'changed'}).status_code==404
        response=client.patch(url+'/messages/source',headers=headers,json={'content':'My name is AJ.'})
        assert response.status_code==200 and response.json()['content']=='My name is AJ.'
        assert not any(m.id=='echo' for m in repo.list_messages(chat['id'],'learner-A'))
        response=client.post(url+'/message',headers=headers,json={'content':'What is my name?'})
        assert response.json()['assistant_message']['content']=='Your name is AJ.'
        assert client.delete(url+'/messages/source',headers=headers).status_code==200
        assert 'AJ' not in json.dumps(client.get(url,headers=headers).json())
        assert client.delete(url,headers={'X-User-Id':'learner-B'}).status_code==404
        assert client.delete(url,headers=headers).status_code==200
        assert client.get(url,headers=headers).status_code==404


def test_cleanup_failure_is_not_acknowledged_and_is_replayed(tmp_path):
    with TestClient(create_app(Settings(_env_file=None,chroma_path=tmp_path))) as client:
        _,repo,_,headers,chat,_=prepare(client)
        class Unavailable:
            def sync(self,user):raise RuntimeError('Local model is unavailable')
        repo.semantic_memory=Unavailable()
        response=client.post('/chat/'+chat['id']+'/forget',headers=headers,json={'target':'my name'})
        assert response.status_code==503 and list(repo.mutations.directory.glob('operation-*.json'))
        assert 'success' in response.json()['detail']
        repo.semantic_memory=None
        restored=client.get('/chat/'+chat['id'],headers=headers)
        assert restored.status_code==200 and 'Amitoj' not in restored.text
        assert not list(repo.mutations.directory.glob('operation-*.json'))


def test_ambiguous_forget_and_negative_instructions_do_not_delete(tmp_path):
    with TestClient(create_app(Settings(_env_file=None,chroma_path=tmp_path))) as client:
        _,repo,_,headers,chat,_=prepare(client)
        assert repo.mutations.control("Don't forget my name.",'learner-A',chat['id']) is None
        response=client.post('/chat/'+chat['id']+'/message',headers=headers,json={'content':'Forget it.'})
        assert 'Do you want me' in response.json()['assistant_message']['content']
        assert any('Amitoj' in m.content for m in repo.list_messages(chat['id'],'learner-A'))


def test_inflight_answer_cannot_restore_forgotten_information(tmp_path):
    with TestClient(create_app(Settings(_env_file=None,chroma_path=tmp_path))) as client:
        service,repo,_,headers,chat,_=prepare(client)
        class RacingTutor:
            def generate_reply(self,messages,system_prompt=None):
                repo.mutations.forget('learner-A',chat['id'],'my name')
                return 'Your name is Amitoj.'
        service._llm_client=RacingTutor()
        response=client.post('/chat/'+chat['id']+'/message',headers=headers,json={'content':'What is my name?'})
        assert response.status_code==409
        assert 'Amitoj' not in json.dumps(client.get('/chat/'+chat['id'],headers=headers).json())


def test_unmatched_forget_does_not_claim_success_or_clear_other_data(tmp_path):
    with TestClient(create_app(Settings(_env_file=None,chroma_path=tmp_path))) as client:
        _,repo,_,headers,chat,_=prepare(client)
        response=client.post('/chat/'+chat['id']+'/message',headers=headers,json={'content':'Forget purple spaceships.'})
        assert "couldn't find" in response.json()['assistant_message']['content']
        assert any('Amitoj' in m.content for m in repo.list_messages(chat['id'],'learner-A'))
