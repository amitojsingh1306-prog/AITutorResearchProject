-- Open in MySQL Workbench against the existing local project connection.
-- Select your project schema in the SCHEMAS panel first. Read-only queries.
-- Scope identifies the project/test namespace; user_id identifies the learner.
SELECT scope, id AS chat_id, user_id, session_id, title
FROM conversations ORDER BY user_id, id;

SELECT scope, id AS message_id, chat_id, user_id, role,
       JSON_UNQUOTE(JSON_EXTRACT(payload, '$.content')) AS content,
       JSON_UNQUOTE(JSON_EXTRACT(payload, '$.session_id')) AS session_id,
       JSON_EXTRACT(payload, '$.memory_trace.response_blueprint') AS response_template
FROM messages ORDER BY chat_id, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.timestamp'));

SELECT s.scope, s.user_id, s.chat_id, s.session_key,
       c.summary_text, c.metadata
FROM memory_sessions AS s
JOIN conversation_summaries AS c
  ON c.scope=s.scope AND c.session_key=s.session_key
ORDER BY s.user_id,s.chat_id;

-- Run delete/update/forget through FastAPI so JSON, MySQL, Chroma, Neo4j,
-- summaries and managed image records stay consistent. Do not manually
-- DELETE SQL rows and assume the chatbot has forgotten the source.
