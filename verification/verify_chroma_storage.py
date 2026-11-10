"""Save test messages through the real repository and inspect real stored vectors."""
from _common import check_main,semantic_demo,DOCUMENTS
import math

def main():
    print('Production path: save_message() → SemanticChatMemory.sync() → embed() → collection.upsert()',flush=True)
    with semantic_demo() as (_,memory,history):
        result=memory.collection.get(ids=[m.id for m in history],include=['documents','metadatas','embeddings'])
        print('Temporary collection:',memory.collection.name)
        assert set(result['ids'])=={key for key,_ in DOCUMENTS}
        expected=dict(DOCUMENTS)
        for key,text,meta,vector in zip(result['ids'],result['documents'],result['metadatas'],result['embeddings']):
            assert text==expected[key] and meta['user_id']=='verification-learner'
            assert len(vector)>0 and all(math.isfinite(float(v)) for v in vector)
            print('\nMESSAGE ID:',key,'\nTEXT:',text,'\nMETADATA:',meta)
            print('STORED VECTOR DIMENSIONS:',len(vector),'\nFIRST 8:',list(vector[:8]))
        print('Text, vector and metadata share the same ID. Test collection is temporary.')

if __name__=='__main__':check_main(main)
