from datetime import datetime,timezone,timedelta
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.models.chat import Message
from backend.services.response_blueprint import load_blueprint,select_template
from backend.tests.test_memory_mutations import Tutor


def test_blueprint_routes_text_summary_and_explicit_attachment():
    base=Message(id='m',chat_id='c',user_id='u',session_id='s',role='user',
                 content='Explain binary search',timestamp=datetime.now(timezone.utc))
    blueprint=load_blueprint()
    assert select_template(base,blueprint)['id']=='normal_content'
    assert select_template(base.model_copy(update={'content':'Summarize our discussion'}),blueprint)['id']=='conversation_summary'
    assert select_template(base.model_copy(update={'image_attachment':{'id':'image'}}),blueprint)['id']=='image_explanation'


def test_summary_refreshes_on_save_and_forget_clears_it(tmp_path):
    settings=Settings(_env_file=None,chroma_path=tmp_path,memory_configuration='summary',
                      working_memory_message_limit=2,prompt_token_budget=6144)
    with TestClient(create_app(settings)) as client:
        service=client.app.state.chat_service;repo=service._repository
        model=Tutor();service._llm_client=model
        headers={'X-User-Id':'blueprint-A'}
        chat=client.post('/chat/create',headers=headers,json={}).json()
        now=datetime.now(timezone.utc)
        for i,text in enumerate(['My goal is to learn binary search.','I prefer numbered steps.','We practice sorted arrays.']):
            repo.save_message(Message(id=f'source-{i}',chat_id=chat['id'],session_id=chat['session_id'],
                user_id='blueprint-A',role='user',content=text,timestamp=now+timedelta(seconds=i)))
        record=json.loads(repo.session_memory._path('blueprint-A',chat['id']).read_text())
        assert 'binary search' in record['rolling_summary']
        assert record['rolling_summary_meta']['source_message_ids']==['source-0']
        response=client.post('/chat/'+chat['id']+'/message',headers=headers,json={'content':'Summarize our discussion'})
        assert response.status_code==201,response.text
        trace=response.json()['assistant_message']['memory_trace']
        assert trace['response_blueprint']['template']=='conversation_summary'
        assert 'Topics, Learner needs, and Next steps' in model.prompts[-1]
        response=client.post('/chat/'+chat['id']+'/message',headers=headers,json={'content':'ok forget abt this conversation'})
        assert response.status_code==201,response.text
        record=json.loads(repo.session_memory._path('blueprint-A',chat['id']).read_text())
        assert 'binary search' not in json.dumps(record)


def test_normal_response_receives_blueprint_without_forcing_json(tmp_path):
    with TestClient(create_app(Settings(_env_file=None,chroma_path=tmp_path,memory_configuration='buffer',prompt_token_budget=6144))) as client:
        service=client.app.state.chat_service;model=Tutor();service._llm_client=model
        h={'X-User-Id':'normal'}
        chat=client.post('/chat/create',headers=h,json={}).json()
        result=client.post('/chat/'+chat['id']+'/message',headers=h,json={'content':'Explain binary search'})
        assert result.status_code==201,result.text
        assert 'brief definition, numbered steps' in model.prompts[-1]
        assert result.json()['assistant_message']['memory_trace']['response_blueprint']['template']=='normal_content'
