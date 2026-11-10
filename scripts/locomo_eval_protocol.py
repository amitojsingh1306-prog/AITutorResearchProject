"""Evaluation-only answer parsing, calendar references and isolated storage."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
import json
import re
import tempfile


ANSWER_CONTRACT = (
    "\nEvaluation format: put only the shortest factual answer inside one "
    "<answer>...</answer> block. Any explanation must be outside it. "
    "If evidence is missing, use <answer>No information available</answer>."
)
TEMPORAL_CONTRACT = (
    "\nA source timestamp is when words were spoken, not necessarily the event date. "
    "Resolve relative dates against that source date, never today's date. "
    "Calendar references below provide arithmetic, not additional event evidence."
)
RESERVED_BYTES = 800
JSON_CONTRACT = (
    "\nEvaluation output: JSON with answer and explanation strings. "
    "answer must contain only the shortest factual conclusion, not metadata. "
    "Keep explanation separate. If unsupported, answer No information available."
)


def extract_answer(raw):
    """Declared model-output boundary only; never inspect a reference answer."""
    opening = re.findall(r"<answer>", raw, re.IGNORECASE)
    closing = re.findall(r"</answer>", raw, re.IGNORECASE)
    matches = re.findall(r"<answer>(.*?)</answer>", raw, re.IGNORECASE | re.DOTALL)
    if len(opening) != 1 or len(closing) != 1 or len(matches) != 1:
        return raw, "invalid_or_missing_boundary"
    core = matches[0].strip()
    if not core:
        return raw, "empty_answer_boundary"
    return core, "valid_boundary"


def calendar_reference(text, timestamp):
    """Explicit day arithmetic, without assigning any date to an event."""
    date = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).date()
    words = {word.lower() for word in re.findall(r"\b(yesterday|today|tomorrow)\b", text, re.I)}
    offsets = {"yesterday": -1, "today": 0, "tomorrow": 1}
    values = [f"{word}={(date + timedelta(days=offset)).isoformat()}"
              for word, offset in offsets.items() if word in words]
    if not values:
        return ""
    return f"Source message date {date.isoformat()}: " + "; ".join(values) + "."


def annotate_relative_dates(text, timestamp):
    """Keep the original words and attach source-anchored calendar arithmetic."""
    date = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).date()
    offsets = {"yesterday": -1, "today": 0, "tomorrow": 1}
    def replace(match):
        resolved = date + timedelta(days=offsets[match.group().lower()])
        human = f"{resolved.day} {resolved.strftime('%B %Y')}"
        return match.group() + " [calendar date: " + human + "]"
    return re.sub(r"\b(yesterday|today|tomorrow)\b", replace, text, flags=re.I)


def extract_json_answer(raw):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return raw, "invalid_json"
    if (not isinstance(value, dict) or set(value) != {"answer", "explanation"}
            or not isinstance(value["answer"], str) or not value["answer"].strip()
            or not isinstance(value["explanation"], str)):
        return raw, "invalid_json_schema"
    return value["answer"].strip(), "valid_json_answer"


@contextmanager
def isolated_storage():
    """Worker must exit before this context closes its temporary directory."""
    with tempfile.TemporaryDirectory(prefix="locomo-evaluation-", dir="/private/tmp") as path:
        yield Path(path)
