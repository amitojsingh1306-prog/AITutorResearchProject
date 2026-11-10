"""Show the actual selected prompt without generating an answer."""
from _common import check_main,semantic_demo,query_message
from backend.services.chat_service import ChatService
import json

def main():
    print('Production function: ChatService._prepare_context(); no Qwen request in this check.',flush=True)
    with semantic_demo() as (repo,memory,_):
        service=ChatService(repo,semantic_memory=memory,memory_configuration='vector',working_memory_limit=1,prompt_token_budget=6144)
        question=query_message();messages,system=service._prepare_context(question)
        trace=question.memory_trace
        print('QUESTION:',question.content,'\nCUTOFF:',trace['minimum_cosine_similarity'])
        for item in trace['retrieved_memories']:
            print(json.dumps({k:item.get(k) for k in ['id','cosine_similarity','included_in_prompt','included_as_history','exclusion_reason','document']}))
            if item.get('included_in_prompt'):assert item['prompt_excerpt'] in system or json.dumps(item['prompt_excerpt']) in system
        assert messages[-1].content==question.content
        assert trace['prompt_token_upper_bound']<=trace['prompt_token_budget']
        print('\nACTUAL SYSTEM PROMPT:\n'+system)
        print('\nACTUAL MESSAGE LIST:')
        for message in messages:print(json.dumps({'id':message.id,'role':message.role,'content':message.content}))
        print('Allowance used:',trace['prompt_token_upper_bound'],'of',trace['prompt_token_budget'],'byte-based units')
        print('This is prepared text. verify_qwen.py separately checks the model connection.')

if __name__=='__main__':check_main(main)
