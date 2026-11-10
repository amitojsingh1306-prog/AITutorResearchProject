# Common memory blueprint

`memory_blueprint.json` is the one blank format for a conversation: learner
fields, messages, image/OCR entries, and a rolling-summary field. Learner fields
and summaries remain blank until a feature explicitly populates them; this is
not automatic profile extraction or summary generation.

Filled session JSONs are written under `chroma_db/session_memory/`. Text messages
and attached OCR records share one record when their `user_id` and `chat_id`
match. The OCR command accepts `--user-id` and `--chat-id`; without a chat ID,
images belong to a separate local image session. Images are copied under that
folder's `images/` directory, not encoded into JSON.

After 3,600 seconds without a new message or image, the backend deletes the
session JSON, owned image copies, chat/message history and corresponding known
Chroma indexes, including durable records linked by source-message ID. The blank
template is never overwritten. New sessions start with empty fields. Corrections
and new replies count as activity; merely viewing chat history does not.

The backend checks every 30 seconds and on relevant history reads, and cleans
expired records at startup. It cannot execute while the computer/application is
off; cleanup resumes at the next start. Removing a session makes its old chat ID
unavailable; start a new conversation afterward.

This policy applies to sessions tracked after this feature is enabled. Existing
untracked chats are not silently scheduled for deletion; their next message
opts that conversation into the common session record. Earlier OCR version-1
records, original screenshots, exports, archives and backups are not deleted.
MySQL/Neo4j have not been connected to this cleanup path. This is logical deletion
from active stores, not forensic secure erasure. Already displayed browser text
or facts repeated in another conversation are not retroactively erased.
