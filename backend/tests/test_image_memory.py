"""Image evidence must remain usable independently of the original file."""

import hashlib
import json
from pathlib import Path

import pytest

from backend.ocr.image_memory import save_image_memory, write_record
from backend.ocr.local_ocr import OCRResult


def test_saved_image_survives_original_removal_and_uses_blueprint(tmp_path):
    source = tmp_path / 'lecture.png'
    source.write_bytes(b'image evidence')
    result = OCRResult('Binary search', [], 623.62, 'model-checksum')
    root = tmp_path / 'memory'
    path, record = save_image_memory(source, result, directory=root)
    source.unlink()
    loaded = json.loads(path.read_text())
    saved = loaded['images'][0]
    image = root / saved['image']['stored_path']
    assert image.read_bytes() == b'image evidence'
    assert saved['image']['sha256'] == hashlib.sha256(image.read_bytes()).hexdigest()
    assert saved['ocr']['text'] == 'Binary search'
    assert saved['generation']['status'] == 'not_requested'
    assert saved['retrieval']['indexed_in_chroma'] is False
    blueprint = json.loads((Path(__file__).resolve().parents[2] / 'memory_blueprint.json').read_text())
    assert loaded.keys() == blueprint.keys()


def test_duplicate_filenames_do_not_overwrite_and_identity_is_preserved(tmp_path):
    source = tmp_path / 'lecture.png'
    source.write_bytes(b'first')
    result = OCRResult('Notes', [], 1, 'checksum')
    first, first_entry = save_image_memory(source, result, directory=tmp_path / 'memory', user_id='A')
    source.write_bytes(b'second')
    second, record = save_image_memory(source, result, directory=tmp_path / 'memory', user_id='A')
    assert first == second and first_entry['id'] != record['id']
    old = json.loads(first.read_text())
    assert old['user_id'] == 'A' and old['chat_id'] is None
    assert (first.parent / first_entry['image']['stored_path']).read_bytes() == b'first'
    assert (second.parent / record['image']['stored_path']).read_bytes() == b'second'


def test_interrupted_record_update_keeps_previous_json(tmp_path):
    path = tmp_path / 'record.json'
    write_record(path, {'status': 'saved'})
    with pytest.raises(TypeError):
        write_record(path, {'invalid': object()})
    assert json.loads(path.read_text()) == {'status': 'saved'}
    assert not list(tmp_path.glob('*.tmp'))
