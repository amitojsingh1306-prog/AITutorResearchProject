"""Show source evidence for your chat in the terminal, without changing it."""
import argparse,json,time
import httpx


def show(message):
    trace=message.get('memory_trace') or {}
    print('\nANSWER:',message['content'])
    print('MODE:',trace.get('memory_configuration'),'STORE:',trace.get('conversation_store'))
    print('RECENT SOURCE IDS:',trace.get('history_message_ids',[]))
    print('SUMMARY:',json.dumps(trace.get('rolling_summary',{})))
    graph=trace.get('graph_memory',{})
    print('GRAPH METHOD:',graph.get('retrieval_method','disabled'))
    for fact in graph.get('facts',[]):
        print('GRAPH:',json.dumps({k:fact.get(k) for k in ['kind','value','relationship_path','source_message_id','included_in_prompt']}))
    items=trace.get('retrieved_memories',[])
    print('VECTOR CANDIDATES (displayed by cosine score; application reserves original-user slots):')
    for rank,item in enumerate(sorted(items,key=lambda x:x['cosine_similarity'],reverse=True),1):
        print(json.dumps({'rank':rank,**{k:item.get(k) for k in ['id','role','cosine_similarity','included_in_prompt','included_as_history','exclusion_reason','document']}}))
    print('Cosine is retrieval similarity, not an answer correctness probability.')
    print('RETRIEVAL MS:',trace.get('retrieval_latency_ms'),'EMBEDDING DIMENSIONS:',trace.get('embedding_dimensions'))
    print('INPUT BYTE ALLOWANCE USED:',trace.get('prompt_token_upper_bound'),'ALLOWANCE:',trace.get('prompt_token_budget'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user',required=True,help='The user ID used by the frontend')
    parser.add_argument('--chat',help='Chat ID; otherwise use this user\'s latest chat')
    parser.add_argument('--follow',action='store_true')
    args=parser.parse_args();last=None
    with httpx.Client(base_url='http://127.0.0.1:8000',headers={'X-User-Id':args.user},timeout=20,trust_env=False) as client:
        try:
            while True:
                chat=args.chat
                if not chat:
                    response=client.get('/chat/list');response.raise_for_status();chats=response.json()
                    if not chats:print('No saved chat for this user.');return
                    chat=chats[0]['id']
                response=client.get('/chat/'+chat);response.raise_for_status()
                answers=[m for m in response.json()['messages'] if m['role']=='assistant']
                if answers and answers[-1]['id']!=last:show(answers[-1]);last=answers[-1]['id']
                if not args.follow:break
                time.sleep(1)
        except KeyboardInterrupt:pass

if __name__=='__main__':main()
