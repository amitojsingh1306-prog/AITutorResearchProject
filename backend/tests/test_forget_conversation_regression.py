import json
import pytest
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.tests.test_memory_mutations import prepare


@pytest.mark.parametrize('command',[
    'ok forget abt this conversation', 'Okay, forget about this chat.',
    'bro please forget our conversation', 'can u forget this convo?',
])
def test_conversation_forget_and_recall_do_not_use_other_chat(tmp_path, command):
    with TestClient(create_app(Settings(_env_file=None,chroma_path=tmp_path))) as client:
        service,repo,tutor,headers,chat,source=prepare(client)
        other=client.post('/chat/create',headers=headers,json={}).json()
        repo.save_message(source.model_copy(update={'id':'other-source','chat_id':other['id'],
            'session_id':other['session_id'],'content':'I am learning chemistry in a separate chat.'}))
        url='/chat/'+chat['id']
        response=client.post(url+'/message/stream',headers=headers,json={'content':command})
        assert response.status_code==200 and 'event: done' in response.text
        assert not tutor.prompts
        assert 'binary search' not in json.dumps(client.get(url,headers=headers).json())
        assert repo.list_messages(other['id'],'learner-A')[0].content.startswith('I am learning chemistry')
        response=client.post(url+'/message',headers=headers,json={'content':'what were we talking abt'})
        answer=response.json()['assistant_message']
        assert answer['content']=="I don't have an earlier conversation saved in this chat to recall."
        assert answer['memory_trace']['generation_used'] is False
        assert not tutor.prompts
        client.post(url+'/message',headers=headers,json={'content':'Explain photosynthesis.'})
        before=len(tutor.prompts)
        client.post(url+'/message',headers=headers,json={'content':'what were we talking abt'})
        assert len(tutor.prompts)==before+1


@pytest.mark.parametrize('text',[
    "ok don't forget this conversation", 'Please do not forget my name.',
    'He said forget this conversation.', '"forget this conversation"',
])
def test_noncommands_do_not_delete(tmp_path,text):
    with TestClient(create_app(Settings(_env_file=None,chroma_path=tmp_path))) as client:
        _,repo,_,_,chat,_=prepare(client)
        assert repo.mutations.control(text,'learner-A',chat['id']) is None
        assert any('Amitoj' in m.content for m in repo.list_messages(chat['id'],'learner-A'))
