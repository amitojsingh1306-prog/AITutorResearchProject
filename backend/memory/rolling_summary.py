"""Deterministic extractive rolling-summary baseline, not LLM fact generation."""

import hashlib
import json

from backend.ocr.image_memory import write_record
from backend.utils.temporal_context import calendar_context


class RollingSummary:
    def __init__(self, repository, recent_turns=6, byte_budget=600, policy=None):
        self.repository = repository
        self.recent_turns = recent_turns
        self.byte_budget = int((policy or {}).get('byte_budget',byte_budget))
        self.excerpt_bytes = int((policy or {}).get('excerpt_bytes',180))
        if self.byte_budget < 1 or self.excerpt_bytes < 1:
            raise ValueError('Summary budgets must be positive')

    def refresh(self,message):
        history=self.repository.list_messages(message.chat_id,message.user_id)
        return self.context(message,history)

    def context(self, message, history):
        older = history[:-self.recent_turns]
        recent = history[-self.recent_turns:]
        if not older:
            sessions = self.repository.session_memory
            with sessions.transaction():
                path = sessions._path(message.user_id, message.chat_id)
                if path.is_file():
                    record = json.loads(path.read_text())
                    if record.get('rolling_summary'):
                        record.update(rolling_summary='', rolling_summary_meta={})
                        sessions.persist(path, record)
            return '', history, {'status': 'not_needed', 'strategy': 'extractive'}
        signature = hashlib.sha256(json.dumps(
            [(m.id, m.content) for m in older], ensure_ascii=False).encode()).hexdigest()
        sessions = self.repository.session_memory
        with sessions.transaction():
            path = sessions._path(message.user_id, message.chat_id)
            if not path.is_file():
                return '', history, {'status': 'session_unavailable'}
            record = json.loads(path.read_text())
            metadata = record.get('rolling_summary_meta', {})
            if metadata.get('source_hash') != signature:
                selected, used, seen = [], 0, set()
                # Prefer original learner statements; tutor excerpts fill remaining space.
                candidates = [m for m in older if m.role == 'user'] or older
                for source in reversed(candidates):
                    excerpt = ' '.join(source.content.split())
                    if excerpt in seen:
                        continue
                    seen.add(excerpt)
                    excerpt = excerpt.encode('utf-8')[:self.excerpt_bytes].decode('utf-8', errors='ignore')
                    line = f'{source.role}: {calendar_context(excerpt,source.timestamp)}'
                    cost = len(line.encode('utf-8')) + 1
                    if used + cost > self.byte_budget:
                        continue
                    selected.append((source.id, line)); used += cost
                selected.reverse()
                record['rolling_summary'] = '\n'.join(line for _, line in selected)
                metadata = {'strategy': 'extractive', 'source_hash': signature,
                            'source_message_ids': [key for key, _ in selected],
                            'older_message_count': len(older), 'recent_message_count': len(recent),
                            'updated_at': sessions.clock().isoformat()}
                record['rolling_summary_meta'] = metadata
                # Updating derived context must not reset the inactivity timer.
                sessions.persist(path, record)
            return record['rolling_summary'], recent, {**metadata, 'status': 'ready'}
