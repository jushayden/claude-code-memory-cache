"""ChromaDB storage for session chunks — via ONE shared HTTP service.

ChromaDB is single-writer: opening the store directly (PersistentClient) from
two processes at once — e.g. two parallel Claude Code sessions, each with its
own memory server — segfaults and can corrupt the vector index. Every client
here therefore connects over HTTP to a single shared Chroma service
(chroma_service.py), which storage auto-starts on demand with a spawn lock.

Env overrides:
  MEMORY_CACHE_CHROMA        store directory (else config.py / default)
  MEMORY_CACHE_CHROMA_HOST   service host (default 127.0.0.1)
  MEMORY_CACHE_CHROMA_PORT   service port (default 8801)
  MEMORY_CACHE_CHROMA_HTTP   "host:port" of an EXTERNALLY managed Chroma —
                             connect there and never auto-start anything
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import chromadb

try:
    from config import CHROMA_DIR, SESSION_COLLECTION
except ImportError:  # not configured yet — same defaults config.example.py documents
    CHROMA_DIR = Path(os.environ.get(
        "MEMORY_CACHE_CHROMA", str(Path(__file__).resolve().parent / "data" / "chromadb")))
    SESSION_COLLECTION = "claude_sessions"
try:
    from config import CHROMA_HOST, CHROMA_PORT
except ImportError:  # config.py predates the shared-service settings
    CHROMA_HOST = os.environ.get("MEMORY_CACHE_CHROMA_HOST", "127.0.0.1")
    CHROMA_PORT = int(os.environ.get("MEMORY_CACHE_CHROMA_PORT", "8801"))

_SERVICE = Path(__file__).resolve().parent / "chroma_service.py"


def _server_up(host: str = None, port: int = None) -> bool:
    s = socket.socket()
    s.settimeout(0.5)
    try:
        return s.connect_ex((host or CHROMA_HOST, port or CHROMA_PORT)) == 0
    except OSError:
        return False
    finally:
        s.close()


def _spawn_service() -> None:
    kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                  stdin=subprocess.DEVNULL, close_fds=True)
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([sys.executable, str(_SERVICE)], **kwargs)


def _ensure_server() -> None:
    """Ensure the shared Chroma service is running. Spawn-locked so parallel
    sessions can't both launch it (two writers = the exact bug this prevents)."""
    if _server_up():
        return
    lock = Path(tempfile.gettempdir()) / f"chroma_service_{CHROMA_PORT}.spawn.lock"
    fd = None
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            stale = (time.time() - lock.stat().st_mtime) > 60
        except OSError:
            stale = True
        if stale:
            try:
                lock.unlink()
                fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except OSError:
                fd = None  # lost the takeover race — fall through to wait

    if fd is None:
        for _ in range(60):  # someone else is spawning; wait for the bind
            if _server_up():
                return
            time.sleep(0.5)
        return

    try:
        if _server_up():
            return
        _spawn_service()
        for _ in range(60):  # up to ~30s for first-start model download etc.
            if _server_up():
                return
            time.sleep(0.5)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            lock.unlink()
        except OSError:
            pass


def get_client():
    ext = os.environ.get("MEMORY_CACHE_CHROMA_HTTP", "").strip()
    if ext:  # externally managed Chroma — connect, never auto-start
        host, _, port = ext.partition(":")
        return chromadb.HttpClient(host=host or "127.0.0.1", port=int(port or 8000))
    _ensure_server()
    return chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)


def get_collection(client):
    return client.get_or_create_collection(
        name=SESSION_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def store_chunk(
    collection,
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
    collection.add(
        documents=[text],
        metadatas=[{
            "session_id": session_id,
            "chunk_type": chunk_type,
            "project": project,
            "timestamp": datetime.now().isoformat(),
            "tags": ",".join(tags) if tags else "",
        }],
        ids=[doc_id],
    )
    return doc_id


def search_sessions(
    collection,
    query: str,
    n_results: int = 5,
    project_filter: str | None = None,
) -> list[dict]:
    """Semantic search across past session chunks."""
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where={"project": project_filter} if project_filter else None,
        include=["documents", "metadatas", "distances"],
    )
    return [{
        "id": results["ids"][0][i],
        "text": results["documents"][0][i],
        "metadata": results["metadatas"][0][i],
        "score": 1 - results["distances"][0][i],
    } for i in range(len(results["ids"][0]))]


def get_session_chunks(collection, session_id: str) -> list[dict]:
    """Get all chunks from a specific session."""
    results = collection.get(
        where={"session_id": session_id},
        include=["documents", "metadatas"],
    )
    return [{
        "id": results["ids"][i],
        "text": results["documents"][i],
        "metadata": results["metadatas"][i],
    } for i in range(len(results["ids"]))]
