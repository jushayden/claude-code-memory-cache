"""ChromaDB storage for session chunks with built-in embeddings."""

import chromadb
from datetime import datetime
from config import CHROMA_DIR, SESSION_COLLECTION


def get_client() -> chromadb.PersistentClient:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    return client.get_or_create_collection(
        name=SESSION_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def store_chunk(
    collection: chromadb.Collection,
    text: str,
    session_id: str,
    chunk_type: str,
    project: str = "",
    tags: list[str] | None = None,
) -> str:
    """Store a meaningful chunk from a session.

    chunk_type: "decision", "learning", "architecture", "preference", "outcome"
    """
    doc_id = f"{session_id}_{datetime.now().strftime('%H%M%S%f')}"

    metadata = {
        "session_id": session_id,
        "chunk_type": chunk_type,
        "project": project,
        "timestamp": datetime.now().isoformat(),
        "tags": ",".join(tags) if tags else "",
    }

    collection.add(documents=[text], metadatas=[metadata], ids=[doc_id])
    return doc_id


def search_sessions(
    collection: chromadb.Collection,
    query: str,
    n_results: int = 5,
    project_filter: str | None = None,
) -> list[dict]:
    """Semantic search across past session chunks."""
    where = {"project": project_filter} if project_filter else None

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": 1 - results["distances"][0][i],
        })
    return hits


def get_session_chunks(
    collection: chromadb.Collection,
    session_id: str,
) -> list[dict]:
    """Get all chunks from a specific session."""
    results = collection.get(
        where={"session_id": session_id},
        include=["documents", "metadatas"],
    )

    chunks = []
    for i in range(len(results["ids"])):
        chunks.append({
            "id": results["ids"][i],
            "text": results["documents"][i],
            "metadata": results["metadatas"][i],
        })
    return chunks
