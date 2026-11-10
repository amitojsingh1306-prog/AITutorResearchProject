"""Show local OCR, managed image metadata, and actual image-template selection."""
from _common import ROOT,USER,isolated_repository,query_message,check_main
from backend.ocr.local_ocr import LocalOCR
from backend.models.chat import ChatMessageRequest
from backend.services.chat_service import ChatService
from backend.services.response_blueprint import load_blueprint,select_template
import json

def main():
    image=ROOT/'backend/tests/fixtures/binary-search-recall.png'
    print('Production path: LocalOCR.extract() → SessionMemory.add_image() → _attach_image() → select_template() → _prepare_context()',flush=True)
    result=LocalOCR().extract(image)
    assert result.text.strip() and 'binary' in result.text.lower()
    print('INPUT:',image,'\nENGINE:',result.engine,'\nLANGUAGE:',result.language)
    print('OCR TEXT:\n'+result.text);print('OCR WORDS:',len(result.words),'OCR MS:',result.elapsed_ms)
    with isolated_repository() as repo:
        path,entry=repo.session_memory.add_image(image,result,user_id=USER,chat_id='demo-chat',question='Explain this image text.')
        record=json.loads(path.read_text());assert any(i['id']==entry['id'] for i in record['images'])
        question=query_message('Explain this image text.')
        service=ChatService(repo,memory_configuration='buffer',prompt_token_budget=6144)
        service._attach_image(question,ChatMessageRequest(content=question.content,image_id=entry['id']))
        template=select_template(question,load_blueprint());assert template['id']=='image_explanation'
        messages,system=service._prepare_context(question)
        assert template['instruction'] in system
        assert question.image_attachment['ocr_text'] in messages[-1].content or json.dumps(question.image_attachment['ocr_text']) in messages[-1].content
        print('SAVED IMAGE ID:',entry['id'],'\nMANAGED COPY:',entry['image']['stored_path'])
        print('SELECTED TEMPLATE:',template['id'],'\nINSTRUCTION:',template['instruction'])
        print('ACTUAL TEXT PREPARED FOR QWEN:\n'+messages[-1].content)
        print('Original fixture remains unchanged; test copy/session are temporary. No Qwen generation or vector indexing in this check.')
        print('OCR is reading text, not general visual understanding. Full image-lineage isolation remains future work.')

if __name__=='__main__':check_main(main)
