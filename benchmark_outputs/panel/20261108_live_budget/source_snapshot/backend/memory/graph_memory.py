"""Local Neo4j evidence graph with explicit, rule-extracted learner assertions.

No model-generated Cypher, no inferred prerequisites, no assistant facts.
The namespace is tied to the source database path so experiments stay isolated.
"""

import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse

TOPICS = {
    'binary search': ('binary search',), 'recursion': ('recursion', 'recursive'),
    'linked lists': ('linked list',), 'arrays': ('array',),
    'sorting': ('sorting',), 'trees': ('tree traversal', 'binary tree'),
    'graphs': ('graph traversal', 'graph algorithm'),
    'dynamic programming': ('dynamic programming',),
    'photosynthesis': ('photosynthesis',),
}

STOP_WORDS=set('a an the and or is was were be been being do does did have has had i me my you your he she they it we our what which who where when why how can could would should about with from into for to of on in at as by that this these those tell said say any please earlier before after'.split())


def retrieval_terms(text):
    return sorted({word for word in re.findall(r'[a-z]{3,}',text.lower()) if word not in STOP_WORDS})


def topics_in(text):
    lowered = text.lower()
    return [name for name, aliases in TOPICS.items() if any(alias in lowered for alias in aliases)]


def extract_facts(messages):
    """Conservative supported patterns; preserve source IDs and explicit corrections."""
    facts, topic_by_chat = [], {}
    for message in sorted(messages, key=lambda m: (m.timestamp, m.id)):
        if message.role != 'user':
            continue
        text = message.content.strip()
        if re.match(r'^(?:what|which|who|where|when|why|how|do|did|can|could|would)\b', text, re.I):
            continue
        found_topics = topics_in(text)
        topic = found_topics[0] if found_topics else topic_by_chat.get(message.chat_id, '')
        if found_topics:
            topic_by_chat[message.chat_id] = topic
        patterns = [
            ('name', r'\bmy name is\s+([^!?\n]+)', ''),
            ('university', r'\b(?:i attend|i study at|my university is)\s+([^!?\n]+)', ''),
            ('preference', r'\bi prefer\s+([^.!?\n]+)', ''),
            ('goal', r'\b(?:my goal is|i want to learn)\s+([^.!?\n]+)', topic),
            ('difficulty', r'\bi\s+(?:keep\s+)?(?:confus\w*|struggle with|am confused about)\s+([^.!?\n]+)', topic),
            ('completed', r'\bi\s+(?:have\s+)?(?:completed|finished|now understand)\s+([^.!?\n]+)', topic),
        ]
        if re.search(r'\bi(?:\s+am|\s*[’\']m) learning\b|\bi study\b', text, re.I) and not re.search(r'\bi study at\b', text, re.I):
            value = topic or re.split(r'[.!?\n]', text)[0][:160]
            facts.append({'kind': 'study', 'value': value, 'topic': topic, 'message': message})
        for kind, pattern, target in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                value = re.split(r'\.\s+(?=(?:I\b|My\b))', match.group(1))[0].strip().rstrip('.')
                facts.append({'kind': kind, 'value': value[:240],
                              'topic': target, 'message': message})
    latest = {}
    for index, fact in enumerate(facts):
        slot = (fact['kind'], '' if fact['kind'] == 'study' else fact['topic'])
        if slot in latest:
            facts[latest[slot]]['active'] = False
        fact['active'] = True; latest[slot] = index
        if fact['kind'] == 'completed' and fact['topic']:
            previous = latest.get(('difficulty', fact['topic']))
            if previous is not None:
                facts[previous]['active'] = False
    return facts


class Neo4jMemory:
    def __init__(self, repository, uri, username, password, database='neo4j'):
        if urlparse(uri).hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('Graph memory only permits a local Neo4j server.')
        from neo4j import GraphDatabase
        self.repository = repository
        self.scope = hashlib.sha256(str(repository._message_file.parent.resolve()).encode()).hexdigest()[:24]
        self.driver = GraphDatabase.driver(uri, auth=(username, password), connection_timeout=5,
                                          max_transaction_retry_time=5, telemetry_disabled=True)
        self.database = database
        self._hashes = {}
        self.driver.verify_connectivity()
        self.run('CREATE CONSTRAINT aitutor_node_key IF NOT EXISTS FOR (n:AITutorGraph) REQUIRE n.key IS UNIQUE')

    def run(self, query, **parameters):
        return self.driver.execute_query(query, parameters_=parameters, database_=self.database).records

    def close(self):
        self.driver.close()

    def sync(self, user_id):
        with self.repository.session_memory.transaction():
            messages = self.repository.list_user_messages(user_id)
            signature = hashlib.sha256(('source-terms-v1'+json.dumps([(m.id, m.chat_id, m.role, m.content, m.timestamp.isoformat()) for m in messages])).encode()).hexdigest()
            if self._hashes.get(user_id) == signature:
                return
            facts = extract_facts(messages)
            key = lambda value: self.scope + ':' + hashlib.sha256((user_id + ':' + value).encode()).hexdigest()
            sources = [{
                'scope':self.scope,'user_id':user_id,'learner_key':key('learner'),
                'session_key':key('chat:'+message.chat_id),'chat_id':message.chat_id,
                'message_key':key('message:'+message.id),'message_id':message.id,
                'content':message.content,'timestamp':message.timestamp.isoformat(),
                'terms':retrieval_terms(message.content),
                'topics':[{'name':topic,'key':key('topic:'+topic)} for topic in topics_in(message.content)],
            } for message in messages if message.role=='user']
            rows = []
            for index, fact in enumerate(facts):
                message = fact['message']
                key = lambda value: self.scope + ':' + hashlib.sha256((user_id + ':' + value).encode()).hexdigest()
                rows.append({
                    'user_id': user_id, 'scope': self.scope, 'learner_key': key('learner'),
                    'session_key': key('chat:' + message.chat_id), 'chat_id': message.chat_id,
                    'message_key': key('message:' + message.id), 'message_id': message.id,
                    'content': message.content, 'timestamp': message.timestamp.isoformat(),
                    'fact_key': key(f'fact:{message.id}:{index}'), 'kind': fact['kind'],
                    'value': fact['value'], 'active': fact['active'], 'topic': fact['topic'],
                    'topic_key': key('topic:' + fact['topic']),
                })
            def write(tx):
                tx.run('MATCH (n:AITutorGraph {scope:$scope, user_id:$user_id}) DETACH DELETE n',
                       scope=self.scope, user_id=user_id).consume()
                # General questions are genuine source records even when they
                # contain no supported personal assertion. MENTIONS indicates
                # text occurrence, not a claim that the learner studies a topic.
                tx.run('''UNWIND $sources AS r
                  MERGE (l:AITutorGraph:Learner {key:r.learner_key}) SET l.scope=r.scope,l.user_id=r.user_id
                  MERGE (s:AITutorGraph:Session {key:r.session_key}) SET s.scope=r.scope,s.user_id=r.user_id,s.chat_id=r.chat_id
                  MERGE (m:AITutorGraph:SourceMessage {key:r.message_key}) SET m.scope=r.scope,m.user_id=r.user_id,m.message_id=r.message_id,m.content=r.content,m.timestamp=r.timestamp,m.terms=r.terms
                  MERGE (l)-[:HAS_SESSION]->(s) MERGE (s)-[:HAS_MESSAGE]->(m)
                  FOREACH (topic IN r.topics |
                    MERGE (t:AITutorGraph:Topic {key:topic.key}) SET t.scope=r.scope,t.user_id=r.user_id,t.name=topic.name
                    MERGE (m)-[:MENTIONS]->(t))''',sources=sources).consume()
                tx.run('''UNWIND $rows AS r
                  MERGE (l:AITutorGraph:Learner {key:r.learner_key}) SET l.scope=r.scope,l.user_id=r.user_id
                  MERGE (s:AITutorGraph:Session {key:r.session_key}) SET s.scope=r.scope,s.user_id=r.user_id,s.chat_id=r.chat_id
                  MERGE (m:AITutorGraph:SourceMessage {key:r.message_key}) SET m.scope=r.scope,m.user_id=r.user_id,m.message_id=r.message_id,m.content=r.content,m.timestamp=r.timestamp
                  MERGE (f:AITutorGraph:Fact {key:r.fact_key}) SET f.scope=r.scope,f.user_id=r.user_id,f.kind=r.kind,f.value=r.value,f.active=r.active,f.timestamp=r.timestamp
                  MERGE (l)-[:HAS_SESSION]->(s) MERGE (s)-[:HAS_MESSAGE]->(m)
                  MERGE (l)-[:HAS_FACT]->(f) MERGE (f)-[:SUPPORTED_BY]->(m)
                  FOREACH (_ IN CASE WHEN r.topic='' THEN [] ELSE [1] END |
                    MERGE (t:AITutorGraph:Topic {key:r.topic_key}) SET t.scope=r.scope,t.user_id=r.user_id,t.name=r.topic
                    MERGE (f)-[:ABOUT]->(t))''', rows=rows).consume()
            with self.driver.session(database=self.database) as session:
                session.execute_write(write)
            self._hashes[user_id] = signature

    def backfill_all(self):
        documents=self.repository._read_json_file(self.repository._message_file)
        users={json.loads(value)['user_id'] for value in documents.values()}
        # Include previously indexed users so deleted source users are cleared.
        users.update(row['user_id'] for row in self.run(
            'MATCH (n:AITutorGraph {scope:$scope}) RETURN DISTINCT n.user_id AS user_id',scope=self.scope))
        for user_id in users:
            self.sync(user_id)

    def retrieve(self, message, limit=6, *, chat_id=None):
        started = time.perf_counter(); self.sync(message.user_id)
        lowered = message.content.lower()
        kinds = []
        for words, kind in [(('name',), 'name'), (('university','college'), 'university'),
                            (('prefer','style'), 'preference'), (('goal',), 'goal'),
                            (('struggl','confus','difficult','misconception'), 'difficulty'),
                            (('completed','finished','mastered'), 'completed'),
                            (('learning','studying','algorithm','topic'), 'study')]:
            if any(word in lowered for word in words): kinds.append(kind)
        focus = topics_in(lowered)
        use_study_topic = not focus and 'difficulty' in kinds
        rows = self.run('''MATCH (l:AITutorGraph:Learner {scope:$scope,user_id:$user_id})
          OPTIONAL MATCH (l)-[:HAS_FACT]->(study:Fact {kind:'study',active:true})-[:ABOUT]->(st:Topic)
          WITH l, collect(DISTINCT st.name) AS study_topics
          MATCH (l)-[:HAS_FACT]->(f:Fact {active:true})-[:SUPPORTED_BY]->(m:SourceMessage)<-[:HAS_MESSAGE]-(s:Session)
          OPTIONAL MATCH (f)-[:ABOUT]->(t:Topic)
          WITH f,m,s,t,study_topics
          WHERE (size($kinds)=0 OR f.kind IN $kinds)
            AND ($chat_id IS NULL OR s.chat_id=$chat_id)
            AND (size($topics)=0 OR t.name IN $topics)
            AND (NOT $use_study_topic OR size(study_topics)=0 OR t.name IN study_topics)
          RETURN DISTINCT f.kind AS kind,f.value AS value,t.name AS topic,m.message_id AS source_message_id,
            m.content AS source_text,m.timestamp AS timestamp,s.chat_id AS chat_id,
            (size(study_topics)>0 AND $use_study_topic AND f.kind='difficulty') AS used_topic_join
          ORDER BY timestamp DESC LIMIT $limit''', scope=self.scope, user_id=message.user_id,
            kinds=kinds, topics=focus, use_study_topic=use_study_topic, limit=limit,chat_id=chat_id)
        items = [dict(row) for row in rows]
        for item in items:
            item['relationship_path'] = ('Learner → study Fact → Topic ← difficulty Fact → SourceMessage'
                                          if item['used_topic_join'] else 'Learner → Fact → SourceMessage')
            item['included_in_prompt'] = False
        method='structured_facts'
        if not items:
            # Graph-backed lexical fallback is explicitly identified. These are
            # quoted SourceMessage nodes, not newly extracted personal facts.
            terms=retrieval_terms(message.content)
            rows=self.run('''MATCH (l:AITutorGraph:Learner {scope:$scope,user_id:$user_id})-[:HAS_SESSION]->(s:Session)-[:HAS_MESSAGE]->(m:SourceMessage)
                WHERE m.message_id <> $current AND ($chat_id IS NULL OR s.chat_id=$chat_id)
                WITH s,m,[word IN $terms WHERE word IN coalesce(m.terms,[])] AS hits
                WHERE size(hits)>0
                RETURN 'source_excerpt' AS kind,m.content AS value,null AS topic,
                  m.message_id AS source_message_id,m.content AS source_text,m.timestamp AS timestamp,
                  s.chat_id AS chat_id,false AS used_topic_join,size(hits) AS lexical_overlap
                ORDER BY lexical_overlap DESC,timestamp DESC LIMIT $limit''',
                scope=self.scope,user_id=message.user_id,current=message.id,terms=terms,limit=min(limit,3),chat_id=chat_id)
            items=[dict(row) for row in rows]
            for item in items:
                item.update(relationship_path='Learner → Session → SourceMessage',included_in_prompt=False)
            method='source_keyword_fallback'
        return items, {'status': 'ready', 'backend': 'neo4j', 'scope': self.scope,
                       'retrieval_method':method,
                       'retrieval_latency_ms': round((time.perf_counter()-started)*1000, 3),
                       'used_topic_join': any(item['used_topic_join'] for item in items), 'facts': items}

    def forget_chat(self, user_id, chat_id):
        # Deletion must work even while other sessions are still active.
        self.run('''MATCH (s:AITutorGraph:Session {scope:$scope,user_id:$user_id,chat_id:$chat_id})
          OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:SourceMessage)
          OPTIONAL MATCH (f:Fact)-[:SUPPORTED_BY]->(m)
          WITH collect(DISTINCT f)+collect(DISTINCT m)+collect(DISTINCT s) AS nodes
          UNWIND nodes AS n DETACH DELETE n''', scope=self.scope,user_id=user_id,chat_id=chat_id)
        self.run('''MATCH (n:AITutorGraph {scope:$scope,user_id:$user_id})
          WHERE NOT (n)--() DETACH DELETE n''', scope=self.scope,user_id=user_id)
        self._hashes.pop(user_id, None)

    def clear_namespace(self):
        self.run('MATCH (n:AITutorGraph {scope:$scope}) DETACH DELETE n', scope=self.scope)
        self._hashes.clear()
