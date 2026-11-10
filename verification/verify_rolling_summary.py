"""Call the actual extractive summary engine and inspect its persisted output."""
from _common import check_main,isolated_repository,query_message,Message,USER
from backend.memory.rolling_summary import RollingSummary
from datetime import datetime,timedelta,timezone
import json

def main():
    print('Production function: backend/memory/rolling_summary.py → RollingSummary.context()',flush=True)
    with isolated_repository() as repo:
        history=[]
        for i in range(8):
            item=Message(id=f'summary-{i}',chat_id='demo-chat',session_id='demo-session',user_id=USER,role='user',content=f'I am learning binary search in Python; practice checkpoint {i}.',timestamp=datetime.now(timezone.utc)+timedelta(microseconds=i))
            repo.save_message(item);history.append(item)
        engine=RollingSummary(repo,recent_turns=2,byte_budget=600)
        summary,recent,trace=engine.context(query_message('Summarize our conversation.'),history)
        record=json.loads(repo.session_memory._path(USER,'demo-chat').read_text())
        assert summary and summary==record['rolling_summary'] and len(summary.encode())<=600
        assert [m.id for m in recent]==['summary-6','summary-7']
        print('ACTUAL SUMMARY:',summary,'\nSUMMARY BYTES:',len(summary.encode()))
        print('RECENT MESSAGE IDS:',[m.id for m in recent]);print('TRACE:',json.dumps(trace))
        print('Saved in the temporary session JSON. This engine selects excerpts; it does not ask Qwen to summarize.')

if __name__=='__main__':check_main(main)
