"""Show real template selection and instructions inserted into model context."""
from _common import check_main,isolated_repository,query_message
from backend.services.response_blueprint import load_blueprint,select_template
from backend.services.chat_service import ChatService

def main():
    blueprint=load_blueprint()
    print('Production functions: load_blueprint(), select_template(), ChatService._prepare_context()')
    with isolated_repository() as repo:
        service=ChatService(repo,memory_configuration='buffer',prompt_token_budget=6144)
        for text,expected in [('Explain binary search.','normal_content'),('Summarize our conversation.','conversation_summary')]:
            question=query_message(text);template=select_template(question,blueprint)
            assert template['id']==expected
            messages,system=service._prepare_context(question)
            assert template['instruction'] in system
            print('\nINPUT:',text,'\nSELECTED TEMPLATE:',template['id'],'\nINSTRUCTION:',template['instruction'])
            print('Instruction found in actual system prompt: YES')
        print('These checks show instruction selection/insertion, not guaranteed Qwen compliance. No model request was sent.')

if __name__=='__main__':check_main(main)
