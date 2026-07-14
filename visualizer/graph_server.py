"""Live 3D graph of your Claude memory — an optional visualizer.

Renders every chunk in your ChromaDB store as a node in an interactive 3D
force graph (semantic k-NN edges, t-SNE layout), and lights up in real time
when a session searches or saves memory (the memory server POSTs activity
here; see the _emit_* helpers in memory_server/server.py).

Run:
    pip install -r requirements-visualizer.txt
    python visualizer/graph_server.py --open

Options:
    --port 8010     port to serve on (default 8010, localhost only)
    --open          open your browser after startup
    --rebuild       force a graph rebuild (otherwise a cached layout is reused)
    --max-nodes N   sample down huge stores for layout speed (default 6000)

Store access: connects to MEMORY_CACHE_CHROMA_HTTP (host:port) as a thin HTTP
client if set — otherwise opens the local store at memory_server's CHROMA_DIR.
NOTE (direct mode): ChromaDB allows only one writer. Building the graph opens
the store read-mostly and caches a snapshot, but if you hit lock/crash issues
while your memory server is running, either run this when sessions are idle or
serve Chroma over HTTP (`chroma run --path <store>` + set MEMORY_CACHE_CHROMA_HTTP).
"""
import argparse
import asyncio
import json
import os
import sys
import webbrowser
from pathlib import Path

import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "memory_server"))
try:
    from config import CHROMA_DIR, SESSION_COLLECTION  # noqa: E402
except ImportError:
    # not configured yet (config.example.py not copied) — same defaults it documents
    CHROMA_DIR = Path(os.environ.get(
        "MEMORY_CACHE_CHROMA",
        str(HERE.parent / "memory_server" / "data" / "chromadb")))
    SESSION_COLLECTION = "claude_sessions"

CACHE = HERE / "data" / "graph_cache.json"
EMB_CACHE = HERE / "data" / "graph_embeddings.npy"
HTML_2D = HERE / "graph.html"
HTML_3D = HERE / "graph3d.html"
HOST = "127.0.0.1"
K = 5  # nearest neighbours per node

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
GRAPH = {"nodes": [], "links": []}
_subs: "set[asyncio.Queue]" = set()
_X = None
_ids: list = []
_ef = None


def _chroma_collection():
    import chromadb
    http = os.environ.get("MEMORY_CACHE_CHROMA_HTTP", "").strip()
    if http:
        host, _, port = http.partition(":")
        client = chromadb.HttpClient(host=host or "127.0.0.1", port=int(port or 8000))
    else:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=SESSION_COLLECTION, metadata={"hnsw:space": "cosine"})


def _embedder():
    global _ef
    if _ef is None:
        from chromadb.utils import embedding_functions
        try:
            _ef = embedding_functions.DefaultEmbeddingFunction()
        except Exception:
            _ef = embedding_functions.ONNXMiniLM_L6_V2()
    return _ef


def _embed(texts):
    ef = _embedder()
    try:
        return np.asarray(ef(texts))
    except TypeError:
        return np.asarray(ef(input=texts))


def build_graph(force: bool = False, max_nodes: int = 6000) -> dict:
    global _X, _ids
    if CACHE.exists() and EMB_CACHE.exists() and not force:
        g = json.loads(CACHE.read_text(encoding="utf-8"))
        _X = np.load(EMB_CACHE)
        _ids = [n["id"] for n in g["nodes"]]
        return g

    from sklearn.neighbors import NearestNeighbors
    from sklearn.manifold import TSNE

    print("building graph: pulling chunks from the store...")
    coll = _chroma_collection()
    d = coll.get(include=["metadatas", "documents"])
    ids, docs, metas = d["ids"], [x or "" for x in d["documents"]], d["metadatas"]
    if len(ids) > max_nodes:
        print(f"  {len(ids)} chunks > --max-nodes {max_nodes}; sampling evenly")
        step = len(ids) / max_nodes
        keep = [int(i * step) for i in range(max_nodes)]
        ids = [ids[i] for i in keep]; docs = [docs[i] for i in keep]; metas = [metas[i] for i in keep]
    if not ids:
        print("  store is empty — the graph will populate as memories are saved")
        return {"nodes": [], "links": []}

    print(f"  embedding {len(docs)} docs (local model, no API)...")
    X = _embed(docs)

    print("  k-NN edges + 3D t-SNE layout...")
    nn = NearestNeighbors(n_neighbors=min(K + 1, len(ids)), metric="cosine").fit(X)
    _, nbr = nn.kneighbors(X)
    seen, links = set(), []
    for i, row in enumerate(nbr):
        for j in row[1:]:
            a, b = (i, int(j)) if i < int(j) else (int(j), i)
            if a != b and (a, b) not in seen:
                seen.add((a, b))
                links.append({"source": ids[a], "target": ids[b]})

    n_comp = 3 if len(ids) > 3 else 2
    pos = TSNE(n_components=n_comp, init="pca",
               perplexity=min(30, max(2, len(ids) - 1) // 3 or 2),
               learning_rate="auto", random_state=42).fit_transform(X)
    pos = (pos - pos.mean(0)) / (pos.std(0) + 1e-9) * 300

    nodes = []
    for i, _id in enumerate(ids):
        m = metas[i] or {}
        t = m.get("chunk_type") or "?"
        if t == "vault_doc" and m.get("source_kind") == "auto_memory":
            fn = (m.get("filename") or "").lower()
            for pref in ("project", "feedback", "reference", "user"):
                if fn.startswith(pref):
                    t = pref
                    break
        nodes.append({
            "id": _id, "type": t, "project": m.get("project") or "",
            "label": " ".join(docs[i].split())[:160],
            "x": float(pos[i, 0]), "y": float(pos[i, 1]),
            "z": float(pos[i, 2]) if n_comp == 3 else 0.0,
        })

    _X, _ids = X, list(ids)
    graph = {"nodes": nodes, "links": links}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(graph), encoding="utf-8")
    np.save(EMB_CACHE, X)
    print(f"  graph: {len(nodes)} nodes, {len(links)} edges -> cached in visualizer/data/")
    return graph


@app.get("/")
async def index():
    return HTMLResponse(HTML_3D.read_text(encoding="utf-8"))


@app.get("/2d")
async def index_2d():
    return HTMLResponse(HTML_2D.read_text(encoding="utf-8"))


@app.get("/graph.json")
async def graph_data():
    return JSONResponse(GRAPH)


@app.post("/emit")
async def emit(req: Request):
    """Pulse: a session searched memory — broadcast the hit ids to browsers."""
    body = await req.json()
    msg = json.dumps({"ids": body.get("ids", []), "query": body.get("query", ""),
                      "kind": body.get("kind", "search")})
    for q in list(_subs):
        try:
            q.put_nowait(msg)
        except Exception:
            pass
    return {"ok": True, "subscribers": len(_subs)}


@app.post("/add")
async def add(req: Request):
    """Live-add: a session saved a new memory — embed, link, broadcast."""
    global _X, _ids
    body = await req.json()
    _id, text = body.get("id"), body.get("text", "") or ""
    if not _id or _id in set(_ids):
        return {"ok": False, "reason": "missing or duplicate id"}
    vec = _embed([text])[0]
    nbr_ids = []
    if _X is not None and len(_X):
        Xn = _X / (np.linalg.norm(_X, axis=1, keepdims=True) + 1e-9)
        vn = vec / (np.linalg.norm(vec) + 1e-9)
        top = np.argsort(-(Xn @ vn))[:K]
        nbr_ids = [_ids[int(i)] for i in top]
    node = {"id": _id, "type": body.get("type", "?"), "project": body.get("project", ""),
            "label": " ".join(text.split())[:160]}
    new_links = [{"source": _id, "target": n} for n in nbr_ids]
    GRAPH["nodes"].append(node)
    GRAPH["links"].extend(new_links)
    _ids.append(_id)
    _X = np.vstack([_X, vec]) if (_X is not None and len(_X)) else np.asarray([vec])
    msg = json.dumps({"kind": "add", "node": node, "links": new_links})
    for q in list(_subs):
        try:
            q.put_nowait(msg)
        except Exception:
            pass
    return {"ok": True, "neighbors": len(nbr_ids)}


@app.get("/events")
async def events():
    q: asyncio.Queue = asyncio.Queue()
    _subs.add(q)

    async def gen():
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _subs.discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Live 3D memory graph")
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--open", action="store_true", help="open browser after start")
    ap.add_argument("--rebuild", action="store_true", help="force graph rebuild")
    ap.add_argument("--max-nodes", type=int, default=6000)
    args = ap.parse_args()

    GRAPH = build_graph(force=args.rebuild, max_nodes=args.max_nodes)
    url = f"http://{HOST}:{args.port}"
    print(f"serving on {url}   (2D view: {url}/2d — kiosk: {url}/?lite&kiosk)")
    if args.open:
        webbrowser.open(url)
    uvicorn.run(app, host=HOST, port=args.port, log_level="warning")
