"""Read-only memory and embedding debug endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Header
import json


router = APIRouter(prefix="/memory", tags=["memory-debug"])


@router.get("/debug")
def memory_debug(
    request: Request,
    user_id: Annotated[str, Header(alias='X-User-Id')],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """Return only this learner's active embedding records."""

    repository = request.app.state.chat_service._repository
    if repository.semantic_memory is None:
        return {'status': 'vector_memory_disabled', 'items': [], 'count': 0}
    collection = repository.semantic_memory.collection
    repository.mutations.resume()
    repository.session_memory.expire()
    result = collection.get(
        limit=limit,
        where={"user_id": user_id},
        include=["documents", "embeddings", "metadatas"],
    )
    items = []
    ids = result.get("ids") or []
    documents = result.get("documents") or []
    raw_embeddings = result.get("embeddings")
    embeddings = raw_embeddings.tolist() if hasattr(raw_embeddings, "tolist") else raw_embeddings
    embeddings = embeddings or []
    metadatas = result.get("metadatas") or []
    for index, item_id in enumerate(ids):
        embedding = embeddings[index] if index < len(embeddings) else []
        items.append(
            {
                "id": item_id,
                "document": documents[index] if index < len(documents) else "",
                "metadata": metadatas[index] if index < len(metadatas) else {},
                "embedding_length": len(embedding),
                "embedding_preview": embedding[:8],
            }
        )
    return {
        "collection": collection.name,
        "embedding_model": repository.semantic_memory.model,
        "count": len(collection.get(where={"user_id": user_id}, include=[])['ids']),
        "items": items,
    }


@router.get('/session/{chat_id}')
def session_details(chat_id: str, request: Request, user_id: Annotated[str, Header(alias='X-User-Id')]):
    service = request.app.state.chat_service
    service.get_chat(chat_id, user_id)
    sessions = service._repository.session_memory
    with sessions.transaction():
        path = sessions._path(user_id, chat_id)
        if not path.exists():
            return {'status': 'not_tracked', 'rolling_summary': ''}
        record = json.loads(path.read_text())
    return {'memory_configuration': service._memory_configuration,
            'rolling_summary': record['rolling_summary'],
            'rolling_summary_meta': record.get('rolling_summary_meta', {}),
            'expires_at': record['expires_at'], 'image_count': len(record['images'])}


@router.get('/graph')
def graph_details(request: Request, user_id: Annotated[str, Header(alias='X-User-Id')]):
    service = request.app.state.chat_service
    graph = service._graph_memory
    if graph is None:
        return {'status': 'not_configured', 'facts': []}
    graph.sync(user_id)
    rows = graph.run('''MATCH (l:AITutorGraph:Learner {scope:$scope,user_id:$user_id})-[:HAS_FACT]->(f:Fact)-[:SUPPORTED_BY]->(m:SourceMessage)
      OPTIONAL MATCH (f)-[:ABOUT]->(t:Topic)
      RETURN f.kind AS kind,f.value AS value,f.active AS active,t.name AS topic,
        m.message_id AS source_message_id,m.content AS source_text ORDER BY m.timestamp LIMIT 100''',
      scope=graph.scope,user_id=user_id)
    return {'status': 'ready', 'backend': 'neo4j', 'scope': graph.scope,
            'facts': [dict(row) for row in rows]}


@router.get('/storage')
def storage_details(request:Request,user_id:Annotated[str,Header(alias='X-User-Id')]):
    repository=request.app.state.chat_service._repository
    sql=getattr(repository,'sql_store',None)
    return {'conversation_store':'mysql' if sql is not None else 'json',
            'chats_for_user':len(repository.list_chats(user_id)),
            'messages_for_user':len(repository.list_user_messages(user_id)),
            'scope':sql.scope if sql is not None else None}
