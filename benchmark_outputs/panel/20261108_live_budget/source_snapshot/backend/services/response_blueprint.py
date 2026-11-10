"""Trusted response templates; conversation text never changes their instructions."""
import json
from pathlib import Path
import re

PATH = Path(__file__).resolve().parents[2] / 'response_blueprint.json'


def load_blueprint():
    data = json.loads(PATH.read_text())
    templates = data['templates']
    ids = [entry['id'] for entry in templates]
    if len(ids) != len(set(ids)) or set(ids) != {
        'normal_content', 'conversation_summary', 'image_explanation'
    }:
        raise ValueError('Invalid response blueprint templates')
    if any(not isinstance(entry['instruction'], str) or not entry['instruction'].strip()
           for entry in templates):
        raise ValueError('Response blueprint instruction is empty')
    return data


def select_template(message, blueprint):
    if message.image_attachment:
        target = 'image_explanation'
    elif re.search(r'\b(?:summari[sz]e|summary|recap)\b', message.content, re.I):
        target = 'conversation_summary'
    else:
        target = 'normal_content'
    return next(entry for entry in blueprint['templates'] if entry['id'] == target)
