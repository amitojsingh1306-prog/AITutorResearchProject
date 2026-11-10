"""Explicit memory edits/forgetting with replayable cleanup and no deleted-text journal."""
import hashlib,json,re
from pathlib import Path
from uuid import uuid4
from backend.memory.graph_memory import extract_facts,TOPICS
from backend.models.chat import Message,ChatSummary
from backend.models.learner import LearnerProfile
from backend.ocr.image_memory import write_record

FIELDS={
 'name':('name',r'my name is','My name is {value}.'),
 'university':('university',r'(?:i attend|i study at|my university is)','I attend {value}.'),
 'preference':('preference',r'i prefer','I prefer {value}.'),
 'goal':('goal',r'(?:my goal is|i want to learn)','My goal is {value}.'),
 'difficulty':('difficulty',r'i\s+(?:keep\s+)?(?:confus\w*|struggle with|am confused about)','I struggle with {value}.'),
}


class MemoryMutationError(RuntimeError):pass


def field_kind(text):
    text=text.lower().strip(' .?!"\'')
    for words,kind in [(('name','my name'),'name'),(('university','my university','college','my college'),'university'),
      (('preference','preferences','my preferences','my preference','explanation style','my explanation style'),'preference'),
      (('goal','goals','my goal','my goals'),'goal'),(('difficulty','my difficulty','misconception','my misconception'),'difficulty')]:
        if text in words:return kind
    return None


def contains(text,term):
    words=re.findall(r'\w+',term.casefold())
    return bool(words) and re.search(r'(?<!\w)'+r'\W+'.join(re.escape(w) for w in words)+r'(?!\w)',text.casefold()) is not None


class MemoryMutations:
    def __init__(self,repo):
        self.repo=repo;self.directory=repo._message_file.parent/'memory_mutations'
        self.directory.mkdir(exist_ok=True,mode=0o700);self.running=False

    def revision(self,user):
        path=self.directory/'revisions.json'
        data=json.loads(path.read_text()) if path.exists() else {}
        return data.get(hashlib.sha256(user.encode()).hexdigest(),0)

    def _bump(self,user):
        path=self.directory/'revisions.json';data=json.loads(path.read_text()) if path.exists() else {}
        key=hashlib.sha256(user.encode()).hexdigest();data[key]=data.get(key,0)+1;write_record(path,data)

    def resume(self):
        with self.repo.session_memory.transaction():
            if self.running:return
            for path in sorted(self.directory.glob('operation-*.json')):
                self._apply(path,json.loads(path.read_text()))

    def _messages(self,user):
        return [Message.model_validate_json(v) for v in self.repo._read_json_file(self.repo._message_file).values()
                if json.loads(v)['user_id']==user]

    def _plan(self,user,remove,updates=None,images=None,profile_fields=None,delete_chats=None):
        messages=self._messages(user);remove=set(remove);updates=updates or {}
        changed=remove|set(updates)
        chats={m.chat_id for m in messages if m.id in changed}
        # Discard generated replies to edited/deleted turns, plus responses whose
        # recorded retrieval/summary evidence depends on those source IDs.
        changed_again=True
        while changed_again:
            changed_again=False
            for chat in {m.chat_id for m in messages}:
                preceding=False
                for m in sorted((m for m in messages if m.chat_id==chat),key=lambda m:m.timestamp):
                    if m.role=='user':preceding=m.id in changed
                    trace=m.memory_trace or {}
                    references=set(trace.get('history_message_ids',[])+trace.get('graph_source_message_ids',[]))
                    references.update(item.get('id') for item in trace.get('retrieved_memories',[]) if item.get('included_in_prompt'))
                    references.update(trace.get('rolling_summary',{}).get('source_message_ids',[]))
                    if m.role=='assistant' and (preceding or bool(references&changed)) and m.id not in remove:
                        remove.add(m.id);changed.add(m.id);chats.add(m.chat_id);changed_again=True
        image_ids=set(images or [])
        image_ids.update(m.image_attachment['id'] for m in messages if m.id in remove and m.image_attachment)
        return {'user_id':user,'remove_ids':sorted(remove),'updates':updates,'image_ids':sorted(image_ids),
                'affected_chats':sorted(chats),'profile_fields':profile_fields or [],'delete_chats':delete_chats or []}

    def submit(self,plan):
        with self.repo.session_memory.transaction():
            self.resume()
            path=self.directory/f'operation-{uuid4().hex}.json'
            write_record(path,plan)
            self._apply(path,plan)
        return {'status':'completed','removed_messages':len(plan['remove_ids']),'updated_messages':len(plan['updates'])}

    def _apply(self,path,plan):
        self.running=True
        try:
            self._bump(plan['user_id'])
            documents=self.repo._read_json_file(self.repo._message_file)
            for key in plan['remove_ids']:
                if key in documents and json.loads(documents[key])['user_id']==plan['user_id']:documents.pop(key)
            for key,content in plan['updates'].items():
                if key in documents:
                    record=json.loads(documents[key])
                    if record['user_id']!=plan['user_id']:raise ValueError('Memory ownership mismatch')
                    record.update(content=content,memory_trace=None);documents[key]=json.dumps(record)
            # Remove diagnostic copies of source excerpts from every surviving turn.
            purge=set(plan['remove_ids'])|set(plan['updates'])
            for key,value in documents.items():
                record=json.loads(value)
                if record['user_id']==plan['user_id']:
                    if record.get('image_attachment',{} ) and record['image_attachment']['id'] in plan['image_ids']:
                        record['image_attachment']=None;purge.add(key)
                    record['memory_trace']=None;documents[key]=json.dumps(record)
            self.repo._write_json_file(self.repo._message_file,documents)
            for memory in self.repo.list_memories(plan['user_id']):
                if memory.source_message_id in set(plan['remove_ids'])|set(plan['updates']):self.repo.delete_memory(memory.id)
            for name in self.repo._client.list_collections():
                if str(name) in {'messages','json_message_embeddings'} or str(name).startswith('semantic_messages_'):
                    if purge:
                        self.repo._client.get_collection(str(name),embedding_function=None).delete(ids=list(purge))
            image_ids=set(plan['image_ids'])
            blank=json.loads((Path(__file__).resolve().parents[2]/'memory_blueprint.json').read_text())['learner']
            for session_path in self.repo.session_memory.directory.glob('*.json'):
                record=json.loads(session_path.read_text())
                if record['user_id']!=plan['user_id']:continue
                remaining=[]
                for entry in record['images']:
                    if entry['id'] in image_ids:
                        image=(self.repo.session_memory.directory/entry['image']['stored_path']).resolve()
                        if image.parent!=(self.repo.session_memory.directory/'images').resolve():raise ValueError('Invalid image path')
                        image.unlink(missing_ok=True)
                    else:
                        # Generated image answers can repeat forgotten context.
                        entry['generation'].update(answer=None,question=None,status='removed',error=None)
                        remaining.append(entry)
                record.update(images=remaining,rolling_summary='',rolling_summary_meta={},learner=blank,
                    messages=[json.loads(v) for v in documents.values() if json.loads(v)['user_id']==plan['user_id'] and json.loads(v)['chat_id']==record['chat_id']])
                self.repo.session_memory.persist(session_path,record)
            chats=self.repo._read_json_file(self.repo._chat_file)
            for key in plan['affected_chats']:
                if key in chats:
                    record=json.loads(chats[key]);record['title']='New conversation';chats[key]=json.dumps(record)
            for key in plan['delete_chats']:
                chats.pop(key,None)
                session_path=self.repo.session_memory._path(plan['user_id'],key)
                sql=getattr(self.repo,'sql_store',None)
                if sql:sql.delete_session(session_path.stem)
                session_path.unlink(missing_ok=True)
            self.repo._write_json_file(self.repo._chat_file,chats)
            if plan['profile_fields']:
                profile=self.repo.get_learner_profile(plan['user_id'])
                defaults=LearnerProfile(user_id=plan['user_id']).model_dump()
                self.repo.save_learner_profile(profile.model_copy(update={key:defaults[key] for key in plan['profile_fields']}))
            semantic=getattr(self.repo,'semantic_memory',None)
            if semantic:semantic.sync(plan['user_id'])
            graph=getattr(self.repo,'graph_memory',None)
            if graph:graph.sync(plan['user_id'])
            path.unlink()
        except Exception as error:
            raise MemoryMutationError('Memory cleanup is pending. It will retry; no success has been confirmed.') from error
        finally:self.running=False

    def edit(self,chat_id,message_id,user,content):
        with self.repo.session_memory.transaction():
            if not content.strip():raise ValueError('Message cannot be blank.')
            messages=self._messages(user)
            old=next((m for m in messages if m.chat_id==chat_id and m.id==message_id),None)
            if old is None:raise LookupError('Message not found')
            if old.role!='user':raise ValueError('Edit the original user message, not a generated answer.')
            result=self.submit(self._plan(user,[],{old.id:content.strip()}))
            return result

    def delete(self,chat_id,message_id,user):
        with self.repo.session_memory.transaction():
            found=next((m for m in self._messages(user) if m.chat_id==chat_id and m.id==message_id),None)
            if found is None:raise LookupError('Message not found')
            return self.submit(self._plan(user,[found.id]))

    def forget(self,user,chat_id,target,scope='user'):
        with self.repo.session_memory.transaction():
            self.resume();messages=self._messages(user)
            if target.lower() in {'this chat','this conversation','our conversation'}:scope='chat'
            selected=messages if scope=='user' else [m for m in messages if m.chat_id==chat_id]
            kind=field_kind(target);facts=extract_facts(selected)
            values={f['value'] for f in facts if f['kind']==kind} if kind else {target}
            if not kind and target.lower() in TOPICS:values.update(TOPICS[target.lower()])
            if kind=='name':
                profile=self.repo.get_learner_profile(user)
                if profile.name:values.add(profile.name)
            broad=target.lower() in {'everything','all','this chat','this conversation'}
            matcher=lambda text:any(contains(text,value) for value in values)
            remove,updates,images=[],{},[]
            for message in selected:
                if broad:remove.append(message.id);continue
                source_facts=[f for f in facts if f['message'].id==message.id and f['kind']==kind]
                if kind and message.role=='user' and source_facts:
                    content=message.content
                    for fact in source_facts:
                        content=re.sub(FIELDS[kind][1]+r'\s+'+re.escape(fact['value'])+r'[.!]?\s*','',content,flags=re.I)
                    if content.strip():updates[message.id]=content.strip()
                    else:remove.append(message.id)
                elif matcher(message.content):remove.append(message.id)
            for path in self.repo.session_memory.directory.glob('*.json'):
                record=json.loads(path.read_text())
                if record['user_id']!=user or (scope=='chat' and record['chat_id']!=chat_id):continue
                for entry in record['images']:
                    if broad or matcher(entry['ocr']['text']):images.append(entry['id'])
            aliases={'name':['name'],'university':[], 'preference':['preferred_explanation_style'],
                     'goal':['learning_goals'],'difficulty':['previous_mistakes']}
            profile_fields=aliases.get(kind,[]) if kind else []
            if broad and scope=='user':profile_fields=['name','field_of_study','learning_goals','completed_topics','current_topics',
                'preferred_explanation_style','previous_mistakes','ongoing_projects','interests']
            defaults=LearnerProfile(user_id=user).model_dump()
            profile=self.repo.get_learner_profile(user).model_dump()
            profile_fields=[key for key in profile_fields if profile[key]!=defaults[key]]
            if not remove and not updates and not images and not profile_fields:
                return {'status':'not_found','removed_messages':0,'updated_messages':0}
            return self.submit(self._plan(user,remove,updates,images,profile_fields))

    def control(self,text,user,chat_id):
        # Strip conversational lead-ins only at the start. Never remove a
        # negation or search inside a quoted/descriptive sentence.
        trimmed=re.sub(r'^(?:(?:ok(?:ay)?|alright|hey|bro|pls)[\s,!]+)+','',text.strip(),flags=re.I)
        update=re.fullmatch(r'(?:please\s+)?(?:update|change|correct)\s+(?:my\s+)?(name|university|college|preference|preferences|explanation style|goal|difficulty)\s+to\s+(.+?)[.!]?\s*',trimmed,re.I)
        if update:
            if not update.group(2).strip():
                return 'Please specify the new value.','What should I update it to?',{'operation':'clarify','status':'no_change'}
            kind=field_kind(update.group(1));result=self.forget(user,chat_id,kind)
            content=FIELDS[kind][2].format(value=update.group(2).strip())
            return content,"I've updated that saved information.",{'operation':'update',**result,'status':'completed'}
        command=re.fullmatch(r'(?:please\s+|(?:can|could) (?:you|u)\s+)?(?:forget|delete|remove)\s+(?:(?:about|abt)\s+)?(.+?)[.!?]?\s*',trimmed,re.I)
        if not command:return None
        target=command.group(1).strip(' .?!')
        if target.lower() in {'it','that','this'}:
            return 'Please clarify what to forget.','Do you want me to forget the last exchange, a specific fact or topic, or this chat?',{'operation':'clarify','status':'no_change'}
        if target.lower() in {'the last exchange','last exchange','the last message','last message','the last thing i told you'}:
            candidates=[m for m in self._messages(user) if m.chat_id==chat_id and m.role=='user' and not (m.memory_trace or {}).get('memory_action')]
            if not candidates:return 'Please forget the last exchange.','There is no earlier exchange saved to remove.',{'operation':'forget','status':'not_found'}
            last=max(candidates,key=lambda m:m.timestamp)
            result=self.submit(self._plan(user,[last.id]))
            return 'Please forget the last exchange.',"I've removed the last exchange from active saved memory.",{'operation':'forget',**result}
        scope='user'
        if target.lower() in {'everything','this chat','this conversation','our conversation','our chat','this convo','this entire conversation','the current conversation'}:
            target='everything';scope='chat'
        elif target.lower() in {'everything about me','all my memories','all my chats'}:target='everything'
        result=self.forget(user,chat_id,target,scope)
        reply=("I've removed that information from your active saved memory." if result['status']=='completed'
               else "I couldn't find matching saved information. Please specify the fact or topic to remove.")
        return 'Please forget the selected saved information.',reply,{'operation':'forget','scope':scope,**result}
