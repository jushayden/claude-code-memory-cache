"""
Configuration for the memory server.

Copy this file to `config.py` and point the paths at your own locations.
Environment variables override the defaults, so you can also leave this as-is
and set MEMORY_CACHE_VAULT / MEMORY_CACHE_CHROMA instead.
"""
import os
from pathlib import Path

# Your Obsidian vault (holds session logs). Created if missing.
VAULT_PATH = Path(os.environ.get(
    "MEMORY_CACHE_VAULT",
    str(Path.home() / "ObsidianVault"),
))
SESSIONS_DIR = VAULT_PATH / "Claude Sessions"

# Local ChromaDB vector store (created automatically if missing).
CHROMA_DIR = Path(os.environ.get(
    "MEMORY_CACHE_CHROMA",
    str(Path(__file__).resolve().parent / "data" / "chromadb"),
))

# ChromaDB collection name for session chunks.
SESSION_COLLECTION = "claude_sessions"

# The shared ChromaDB HTTP service. One service owns the store; every memory
# server and the visualizer connect as thin HTTP clients, so parallel Claude
# Code sessions are safe (direct multi-process access segfaults ChromaDB).
# storage.py auto-starts the service on demand — you rarely touch these.
CHROMA_HOST = os.environ.get("MEMORY_CACHE_CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.environ.get("MEMORY_CACHE_CHROMA_PORT", "8801"))
