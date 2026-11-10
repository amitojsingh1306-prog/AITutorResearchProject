"""Call the real embedding method and display returned document/query vectors."""
from _common import check_main,embedding_connection,SemanticChatMemory
from uuid import uuid4
import time

def main():
    settings,connection=embedding_connection()
    marker='VERIFY_NOMIC_'+uuid4().hex[:8]
    text=f'{marker}: I am learning binary search in Python.'
    print('Production function: backend/memory/semantic_chat.py → SemanticChatMemory.embed()',flush=True)
    print('POST',connection.base_url+'/embeddings','MODEL',settings.embedding_model,flush=True)
    print('Log marker:',marker,flush=True)
    for query in (False,True):
        prefix='search_query: ' if query else 'search_document: '
        print('\nINPUT:',prefix+text,flush=True);start=time.perf_counter()
        vector=SemanticChatMemory.embed(connection,[text],query=query)[0]
        print('Returned dimensions:',len(vector));print('First 8 coordinates:',vector[:8])
        print('Local request ms:',round((time.perf_counter()-start)*1000,2),flush=True)
    print('Match the marker in LM Studio Developer Logs. No stored conversation was created.')

if __name__=='__main__':check_main(main)
