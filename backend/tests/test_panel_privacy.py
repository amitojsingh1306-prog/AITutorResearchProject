from types import SimpleNamespace
from fastapi.testclient import TestClient
import pytest
from backend.config import Settings
from backend.main import create_app
from backend.utils.local_endpoints import require_loopback, validate_model_endpoints
from backend.utils.temporal_context import calendar_context


@pytest.mark.parametrize('url', ['https://example.com/v1','http://127.0.0.1.evil.test',
    'http://192.168.1.2/v1','http://localhost@external.test','file:///tmp/model',
    'http://localhost/v1?forward=external'])
def test_nonlocal_endpoints_rejected(url):
    with pytest.raises(ValueError):require_loopback(url)


@pytest.mark.parametrize('url',['http://127.0.0.1:1234/v1','http://localhost:1234/v1','http://[::1]:1234/v1'])
def test_loopback_accepted(url):
    assert require_loopback(url)==url


def test_cloud_fallback_is_not_silently_used():
    with pytest.raises(ValueError):
        validate_model_endpoints(Settings(_env_file=None,lmstudio_base_url='',groq_api_key='test'))


def test_calendar_hints_handle_boundaries_without_changing_source_words():
    text=calendar_context('I finished yesterday.','2024-03-01T10:00:00+00:00')
    assert text.startswith('I finished yesterday.') and 'yesterday=2024-02-29' in text
    assert 'tomorrow=2027-01-01' in calendar_context('Tomorrow','2026-12-31T10:00:00+00:00')
    assert calendar_context('No relative date','2026-11-07T00:00:00+00:00')=='No relative date'
    assert 'yesterday=' not in calendar_context('Read this\nOCR image text: Yesterday we met.', '2026-11-07T00:00:00+00:00')


def test_embedding_inspector_requires_and_filters_identity(tmp_path):
    with TestClient(create_app(Settings(_env_file=None,chroma_path=tmp_path,memory_configuration='buffer'))) as client:
        repo=client.app.state.chat_service._repository
        collection=repo._client.get_or_create_collection('privacy_fixture',embedding_function=None)
        collection.add(ids=['a','b'],embeddings=[[1.,0.],[0.,1.]],
            documents=['own statement','private second learner'],metadatas=[{'user_id':'A'},{'user_id':'B'}])
        repo.semantic_memory=SimpleNamespace(collection=collection,model='fixture')
        assert client.get('/memory/debug').status_code==422
        reply=client.get('/memory/debug',headers={'X-User-Id':'A'})
        assert reply.status_code==200 and reply.json()['count']==1
        assert reply.json()['items'][0]['document']=='own statement'
        assert 'private second learner' not in reply.text


def test_unsupported_identity_is_not_delegated_to_a_hallucinating_model(tmp_path):
    with TestClient(create_app(Settings(_env_file=None,chroma_path=tmp_path,memory_configuration='buffer'))) as client:
        service=client.app.state.chat_service
        class InventingModel:
            def generate_reply(self,*args,**kwargs):raise AssertionError('Unsupported identity reached the model')
            def stream_reply(self,*args,**kwargs):raise AssertionError('Unsupported identity reached the model')
        service._llm_client=InventingModel()
        headers={'X-User-Id':'unknown'}
        chat=client.post('/chat/create',headers=headers,json={}).json()
        response=client.post('/chat/'+chat['id']+'/message',headers=headers,json={'content':'What is my name?'})
        assert response.status_code==201
        assert response.json()['assistant_message']['content']=="I don't have your name saved."
        stream=client.post('/chat/'+chat['id']+'/message/stream',headers=headers,json={'content':'Which university do I attend?'})
        assert 'event: done' in stream.text and "I don't have your university saved." in stream.text
