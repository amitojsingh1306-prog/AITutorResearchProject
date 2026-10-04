"""Read-only memory and embedding debug endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request


router = APIRouter(prefix="/memory", tags=["memory-debug"])


@router.get("/debug")
def memory_debug(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """Return a small preview of JSON-derived Chroma embeddings."""

    repository = request.app.state.chat_service._repository
    collection = repository.get_json_embedding_collection()
    result = collection.get(
        limit=limit,
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
        "collection": "json_message_embeddings",
        "count": collection.count(),
        "items": items,
    }
