"""Call the same local generation adapter used by the tutor."""
from _common import check_main,embedding_connection
from backend.llm.groq_client import GroqClient
from uuid import uuid4

def main():
    settings,connection=embedding_connection();marker='VERIFY_QWEN_'+uuid4().hex[:8]
    print('Production function: backend/llm/groq_client.py → GroqClient.generate_text()',flush=True)
    print('Historical class name; destination is LOCAL:',connection.base_url+'/chat/completions',flush=True)
    print('MODEL:',settings.lmstudio_model,'LOG MARKER:',marker,flush=True)
    client=GroqClient(api_key='local',base_url=connection.base_url,model=settings.lmstudio_model,num_predict=16,temperature=0.1)
    answer=client.generate_text(system_prompt='Follow the requested short output format.',user_content=f'{marker}. Reply with exactly LOCAL_QWEN_OK.',temperature=0.1)
    print('ACTUAL MODEL RESPONSE:',answer)
    print('This proves a request/response, not the full retrieval flow or general accuracy.')

if __name__=='__main__':check_main(main)
