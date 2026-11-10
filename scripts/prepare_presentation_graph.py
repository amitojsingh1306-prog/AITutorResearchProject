"""Create a labelled, isolated binary-search presentation fixture in local Neo4j.

This is example input, not a benchmark result or a rewrite of private history.
Uses the actual repository and graph extractor; never touches the live namespace.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,timedelta,timezone
import json
from backend.config import Settings
from backend.database.factory import create_repository
from backend.memory.graph_memory import Neo4jMemory
from backend.models.chat import ChatSummary,Message

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'.local/presentation_binary_search'
QUERY='''MATCH (n:PresentationDemo {dataset: 'binary-search'})
OPTIONAL MATCH (n)-[r]->(m:PresentationDemo {dataset: 'binary-search'})
RETURN n, r, m;'''


def main():
    settings=Settings()
    demo=settings.model_copy(update={'chroma_path':DIRECTORY,'mysql_enabled':True})
    repo=create_repository(demo)
    credentials=json.loads(settings.graph_credentials_file.read_text())
    graph=Neo4jMemory(repo,settings.graph_uri,credentials['username'],credentials['password'],settings.graph_database)
    repo.graph_memory=graph
    try:
        # Reset this fixture only, preserving every node in the live namespace.
        graph.clear_namespace()
        repo.sql_store.clear_namespace()
        for path in repo.session_memory.directory.glob('*.json'):path.unlink()
        now=datetime.now(timezone.utc)
        chat=ChatSummary(id='presentation-binary-search',user_id='presentation-demo',
            session_id='presentation-session',title='Binary search — presentation example',
            created_at=now,updated_at=now)
        repo.save_chat(chat)
        examples=[
            "My name is Amitoj. I'm learning binary search in Python. I prefer short explanations using numbered steps.",
            "I keep confusing low, high, and mid. Remember that this is my main difficulty.",
            "My goal is to implement binary search correctly in Python.",
        ]
        for index,text in enumerate(examples):
            repo.save_message(Message(id=f'presentation-source-{index}',chat_id=chat.id,user_id=chat.user_id,
                session_id=chat.session_id,role='user',content=text,timestamp=now+timedelta(seconds=index)))
        graph.sync(chat.user_id)
        graph.run('''MATCH (n:AITutorGraph {scope:$scope})
          SET n:PresentationDemo,n.dataset='binary-search',n.presentation_example=true
          SET n.name=CASE
            WHEN n:Learner THEN 'Amitoj (example)'
            WHEN n:Session THEN 'Binary-search lesson'
            WHEN n:SourceMessage THEN CASE
              WHEN n.content CONTAINS 'My name' THEN 'Introduction and preference'
              WHEN n.content CONTAINS 'confusing' THEN 'Stated difficulty'
              ELSE 'Learning goal' END
            WHEN n:Fact THEN n.kind+': '+n.value
            ELSE n.name END''',scope=graph.scope)
        nodes=graph.run('MATCH (n:PresentationDemo {dataset:$dataset,scope:$scope}) RETURN count(n) AS n',
                        dataset='binary-search',scope=graph.scope)[0]['n']
        relationships=graph.run('MATCH (:PresentationDemo {dataset:$dataset,scope:$scope})-[r]->(:PresentationDemo) RETURN count(r) AS n',
                                dataset='binary-search',scope=graph.scope)[0]['n']
        assert nodes>0 and relationships>0
        # A fixture input must never include messages from a real learner account.
        foreign=graph.run('MATCH (n:PresentationDemo {dataset:$dataset}) WHERE n.user_id<>$user RETURN count(n) AS n',
                          dataset='binary-search',user=chat.user_id)[0]['n']
        assert foreign==0
        report={'type':'Labelled presentation example; not a measured benchmark result',
                'dataset':'binary-search','scope':graph.scope,'source_messages':examples,
                'nodes':nodes,'relationships':relationships,'private_history_modified':False,
                'neo4j_query':QUERY}
        (ROOT/'deliverables').mkdir(exist_ok=True)
        (ROOT/'deliverables/presentation_graph.json').write_text(json.dumps(report,indent=2))
        (ROOT/'deliverables/presentation_graph.cypher').write_text(QUERY+'\n')
        print(json.dumps({'nodes':nodes,'relationships':relationships,'query':QUERY},indent=2))
    finally:
        graph.close();repo.sql_store.close()


if __name__=='__main__':main()
