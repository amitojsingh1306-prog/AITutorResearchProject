"""Local dense indexing and retrieval used by live chat."""

import hashlib
import math
import time
from threading import RLock

import httpx


class SemanticChatMemory:
    def __init__(self, repository, base_url: str, model: str):
        self.repository = repository
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.lock = RLock()
        suffix = hashlib.sha256(model.encode()).hexdigest()[:12]
        self.collection = repository._client.get_or_create_collection(
            name=f"semantic_messages_{suffix}", embedding_function=None,
            metadata={"hnsw:space": "cosine", "embedding_model": model},
        )

    def embed(self, texts: list[str], *, query=False):
        prefix = "search_query: " if query else "search_document: "
        response = httpx.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "input": [prefix + text for text in texts]},
            timeout=60, trust_env=False,
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda row: row["index"])
        vectors = [row["embedding"] for row in data]
        if len(vectors) != len(texts) or any(
            not v or not all(math.isfinite(x) for x in v) or not any(v) for v in vectors
        ):
            raise ValueError("Local embedding server returned invalid vectors")
        return vectors

    def sync(self, user_id: str):
        """Reconcile saved JSON, including content updates and deletions."""
        with self.lock:
            valid = {m.id: m for m in self.repository.list_user_messages(user_id)
                     if m.content.strip()}
            stored = self.collection.get(where={"user_id": user_id}, include=["metadatas"])
            hashes = {key: meta.get("content_hash") for key, meta in
                      zip(stored["ids"], stored["metadatas"] or [])}
            removed = list(set(hashes) - set(valid))
            if removed:
                self.collection.delete(ids=removed)
            def searchable(message):
                attachment = message.image_attachment
                return message.content + ('\nOCR image text: ' + attachment['ocr_text'] if attachment else '')
            pending = [m for m in valid.values() if hashes.get(m.id) !=
                       hashlib.sha256(searchable(m).encode()).hexdigest()]
            for offset in range(0, len(pending), 16):
                batch = pending[offset:offset + 16]
                vectors=self.embed([searchable(m) for m in batch])
                self.collection.upsert(
                    ids=[m.id for m in batch], documents=[searchable(m) for m in batch],
                    embeddings=vectors,
                    metadatas=[{
                        "user_id": m.user_id, "chat_id": m.chat_id, "role": m.role,
                        "timestamp": m.timestamp.isoformat(),
                        "content_hash": hashlib.sha256(searchable(m).encode()).hexdigest(),
                    } for m in batch],
                )
                sql=getattr(self.repository,'sql_store',None)
                if sql is not None:
                    for message,vector in zip(batch,vectors):
                        sql.embedding_synced(message.id,self.collection.name,self.model,len(vector),
                                             hashlib.sha256(searchable(message).encode()).hexdigest())
                for message in batch:
                    if message.image_attachment:
                        sessions = self.repository.session_memory
                        entry, _ = sessions.get_image(message.user_id, message.chat_id, message.image_attachment['id'])
                        entry['retrieval'].update(indexed_in_chroma=True, source_message_id=message.id)
                        sessions.update_image(sessions._path(message.user_id, message.chat_id), entry)
            sql=getattr(self.repository,'sql_store',None)
            if sql is not None:
                missing=(set(hashes)&set(valid))-sql.embedding_ids(self.collection.name)
                if missing:
                    existing=self.collection.get(ids=list(missing),include=['embeddings','metadatas'])
                    for key,vector,metadata in zip(existing['ids'],existing['embeddings'],existing['metadatas']):
                        sql.embedding_synced(key,self.collection.name,self.model,len(vector),metadata['content_hash'])

    def retrieve(self, message, limit=6, *, chat_id=None):
        started = time.perf_counter()
        self.sync(message.user_id)
        sync_ms = (time.perf_counter() - started) * 1000
        search_started = time.perf_counter()
        embedding = self.embed([message.content], query=True)[0]
        items = []
        # Reserve candidate slots for original user statements, rather than
        # letting repeated assistant denials crowd them out of retrieval.
        for role, slots in (("user", 4), ("assistant", 2)):
            filters=[{"user_id":message.user_id},{"role":role}]
            if chat_id is not None:filters.append({'chat_id':chat_id})
            result = self.collection.query(
                query_embeddings=[embedding], n_results=limit + 1,
                where={"$and": filters},
                include=["documents", "metadatas", "distances"],
            )
            role_items = []
            for key, document, metadata, distance in zip(
                result["ids"][0], result["documents"][0],
                result["metadatas"][0], result["distances"][0],
            ):
                if key != message.id:
                    role_items.append({"id": key, "document": document, **metadata,
                                       "cosine_similarity": round(1 - distance, 6)})
            items.extend(role_items[:slots])
        return items[:limit], {
            "collection": self.collection.name, "embedding_model": self.model,
            "embedding_dimensions": len(embedding), "sync_ms": round(sync_ms, 3),
            "retrieval_latency_ms": round((time.perf_counter() - search_started) * 1000, 3),
            "retrieved_memories": items[:limit],
        }


def token_upper_bound(text: str) -> int:
    """Conservative UTF-8 byte bound, including a message-format allowance."""
    return len(text.encode("utf-8")) + 16
