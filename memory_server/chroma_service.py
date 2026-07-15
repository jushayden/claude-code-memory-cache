"""The single shared ChromaDB HTTP server.

ChromaDB allows exactly ONE writer process on a store. But Claude Code spawns
one memory MCP server per session — run two sessions in parallel with direct
(PersistentClient) access and you get segfaults and, eventually, a corrupted
vector index. The fix: run one Chroma HTTP service that owns the store, and
have every memory server (and the visualizer) connect as thin HTTP clients.

You normally never run this yourself — storage.py auto-starts it on demand
(spawn-locked, so parallel sessions can't double-start it). To run it manually
or as a login service:  python memory_server/chroma_service.py

Idempotent by port bind: if the port is already taken, this exits immediately.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from storage import CHROMA_DIR, CHROMA_HOST, CHROMA_PORT  # noqa: E402


def main() -> None:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    args = ["chroma", "run", "--path", str(CHROMA_DIR),
            "--host", CHROMA_HOST, "--port", str(CHROMA_PORT)]
    try:
        import chromadb_rust_bindings          # chromadb >= 1.x
        chromadb_rust_bindings.cli(args)
    except ImportError:
        subprocess.run(args)                   # fall back to `chroma` on PATH


if __name__ == "__main__":
    main()
