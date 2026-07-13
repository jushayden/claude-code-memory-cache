"""
Configuration for the memory server.

Copy this file to `config.py` and point the paths at your own locations.
Environment variables override the defaults, so you can also leave this as-is
and set CLAUDE_BRAIN_VAULT / CLAUDE_BRAIN_CHROMA instead.
"""
import os
from pathlib import Path

# Your Obsidian vault (holds session logs). Created if missing.
VAULT_PATH = Path(os.environ.get(
    "CLAUDE_BRAIN_VAULT",
    str(Path.home() / "ObsidianVault"),
))
SESSIONS_DIR = VAULT_PATH / "Claude Sessions"

# Local ChromaDB vector store (created automatically if missing).
CHROMA_DIR = Path(os.environ.get(
    "CLAUDE_BRAIN_CHROMA",
    str(Path(__file__).resolve().parent / "data" / "chromadb"),
))

# ChromaDB collection name for session chunks.
SESSION_COLLECTION = "claude_sessions"
