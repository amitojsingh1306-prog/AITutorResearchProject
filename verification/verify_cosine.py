"""Independently compare cosine math against real Chroma distances."""
from _common import check_main,semantic_demo,query_message,USER
import math

def cosine(left,right):
    dot=math.fsum(float(a)*float(b) for a,b in zip(left,right))
    left_norm=math.sqrt(math.fsum(float(a)**2 for a in left))
    right_norm=math.sqrt(math.fsum(float(b)**2 for b in right))
    if len(left)!=len(right) or not left_norm or not right_norm:raise ValueError('Invalid vector dimensions/norms')
    return dot/(left_norm*right_norm),dot,left_norm,right_norm

def main():
    print('Production code: SemanticChatMemory.embed(), retrieve(); Chroma cosine collection.',flush=True)
    with semantic_demo() as (_,memory,_):
        question=query_message();q=memory.embed([question.content],query=True)[0]
        matches=memory.collection.query(query_embeddings=[q],n_results=3,where={'user_id':USER},include=['documents','distances'])
        print('QUERY:',question.content,'\nQUERY VECTOR FIRST 8:',q[:8])
        print('cosine = dot(query, stored) / (norm(query) * norm(stored))')
        for rank,(key,text,distance) in enumerate(zip(matches['ids'][0],matches['documents'][0],matches['distances'][0]),1):
            stored=memory.collection.get(ids=[key],include=['embeddings'])['embeddings'][0]
            manual,dot,qn,dn=cosine(q,stored);reported=1-float(distance)
            assert math.isclose(manual,reported,abs_tol=2e-5),(manual,reported)
            print(f'\nRANK {rank} — {key}: {text}')
            print(f'dot={dot:.8f}; query norm={qn:.8f}; stored norm={dn:.8f}')
            print(f'manual cosine={manual:.8f}; Chroma distance={distance:.8f}; 1-distance={reported:.8f}')
        items,_=memory.retrieve(question)
        print('\nActual retrieve() candidates (role slots apply, not a calibrated confidence ranking):')
        for item in items:print(item['id'],item['cosine_similarity'])
        print('Close numerical agreement verifies the distance conversion, not factual correctness.')

if __name__=='__main__':check_main(main)
