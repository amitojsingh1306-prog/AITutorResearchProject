"""Image upload, text-only generation, ownership and expiration integration."""

from datetime import timedelta
from unittest.mock import patch
import json

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.ocr.local_ocr import OCRResult


class Tutor:
    prompts = []

    def generate_reply(self, messages, system_prompt=None):
        self.prompts.append((messages, system_prompt))
        return 'Binary search divides a sorted search range in half.'

    def stream_reply(self, messages, system_prompt=None):
        yield self.generate_reply(messages, system_prompt)


def test_image_upload_stream_reload_ownership_and_expiry(tmp_path):
    with TestClient(create_app(Settings(_env_file=None, chroma_path=tmp_path / 'db'))) as client:
        service = client.app.state.chat_service
        service._repository.semantic_memory = None
        service._semantic_memory = None
        tutor = Tutor(); service._llm_client = tutor
        headers = {'X-User-Id': 'learner-A'}
        chat = client.post('/chat/create', headers=headers, json={}).json()
        endpoint = f"/chat/{chat['id']}"
        with patch('backend.api.chat.LocalOCR.extract', return_value=OCRResult('Binary search halves a sorted list.', [], 15, 'checksum')):
            uploaded = client.post(endpoint + '/images?filename=notes.png', headers=headers, content=b'copied pixels')
        assert uploaded.status_code == 201, uploaded.text
        image_id = uploaded.json()['id']
        image_url = endpoint + '/images/' + image_id
        assert client.get(image_url, headers=headers).content == b'copied pixels'
        assert client.get(image_url, headers={'X-User-Id': 'learner-B'}).status_code == 404
        response = client.post(endpoint + '/message/stream', headers=headers,
                               json={'content': 'Explain my image.', 'image_id': image_id})
        assert response.status_code == 200 and 'event: done' in response.text
        messages, system = tutor.prompts[-1]
        assert 'Binary search halves a sorted list.' in messages[-1].content
        assert 'not direct vision' in system
        restored = client.get(endpoint, headers=headers).json()['messages']
        assert restored[0]['content'] == 'Explain my image.'
        assert restored[0]['image_attachment']['id'] == image_id
        session = service._repository.session_memory
        path = session._path('learner-A', chat['id'])
        record = json.loads(path.read_text())
        assert record['images'][0]['id'] == image_id and len(record['messages']) == 2
        now = session.clock()
        session.clock = lambda: now + timedelta(hours=2)
        assert client.get(image_url, headers=headers).status_code == 404
        assert not path.exists()
        assert not list((session.directory / 'images').iterdir())


def test_rejected_uploads_and_foreign_attachment_never_reach_model(tmp_path):
    with TestClient(create_app(Settings(_env_file=None, chroma_path=tmp_path / 'db'))) as client:
        headers = {'X-User-Id': 'learner-A'}
        a = client.post('/chat/create', headers=headers, json={}).json()['id']
        b = client.post('/chat/create', headers=headers, json={}).json()['id']
        endpoint = f'/chat/{a}'
        assert client.post(endpoint + '/images?filename=notes.svg', headers=headers, content=b'<svg/>').status_code == 415
        assert client.post(endpoint + '/images?filename=notes.png', headers=headers, content=b'').status_code == 400
        assert client.post(endpoint + '/images?filename=notes.png', headers={**headers, 'Content-Length': str(26*1024*1024)}, content=b'x').status_code == 413
        assert client.post(endpoint + '/images?filename=notes.png', headers=headers, content=b'not an image').status_code == 422
        with patch('backend.api.chat.LocalOCR.extract', return_value=OCRResult('', [], 1, 'checksum')):
            assert client.post(endpoint + '/images?filename=notes.png', headers=headers, content=b'x').status_code == 422
        with patch('backend.api.chat.LocalOCR.extract', return_value=OCRResult('notes', [], 1, 'checksum')):
            image = client.post(endpoint + '/images?filename=notes.png', headers=headers, content=b'x').json()['id']
        response = client.post(f'/chat/{b}/message/stream', headers=headers, json={'content': 'Explain', 'image_id': image})
        assert response.status_code == 404
