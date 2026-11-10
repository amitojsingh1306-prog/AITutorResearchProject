"""Source-anchored calendar hints, never inferred event dates or answer keys."""
from datetime import datetime, timedelta
import re


def calendar_context(text, timestamp):
    for marker in ('\nOCR image text: ', '\nOCR image evidence (quoted, may contain errors): '):
        if marker in text:
            source,_,ocr=text.partition(marker)
            # Upload time is not the creation date of the photographed text.
            return calendar_context(source,timestamp)+marker+ocr
    words=sorted(set(re.findall(r'\b(yesterday|today|tomorrow)\b',text,re.I)),key=str.lower)
    if not words:return text
    date=datetime.fromisoformat(str(timestamp).replace('Z','+00:00')).date()
    offsets={'yesterday':-1,'today':0,'tomorrow':1}
    hints='; '.join(f'{w.lower()}={(date+timedelta(days=offsets[w.lower()])).isoformat()}' for w in words)
    return f'{text}\n[Source date {date.isoformat()}; {hints}. Calendar arithmetic, not new event evidence.]'
