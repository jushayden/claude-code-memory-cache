"""BM25 + vector hybrid retrieval for memory_search.

Pure-vector search blurs exact-keyword queries (error strings, env var names,
IDs) that embeddings treat as near-noise. A BM25 pass over the same documents
catches those, and Reciprocal Rank Fusion merges the two rankings.

The BM25 index lives in RAM — the store is small (~1k docs), so builds take
milliseconds and there is no extra index file to keep in sync. It rebuilds
whenever the collection count changes (other processes save memories too) or
every _MAX_AGE_S as a safety net for same-count edits.
"""
import math
import re
import threading
import time

from storage import search_sessions

_TOKEN = re.compile(r"\w+")
_K1, _B = 1.5, 0.75
_RRF_K = 60
_MAX_AGE_S = 600

_lock = threading.Lock()
_cached = None  # (collection_count, built_at, _Bm25)


def _tokenize(text):
    return _TOKEN.findall(text.lower())


class _Bm25:
    def __init__(self, records):
        """records: list of (id, text, metadata)."""
        self.records = records
        self.n = len(records)
        self.tf, self.doc_len, self.df = [], [], {}
        for _, text, _ in records:
            toks = _tokenize(text or "")
            self.doc_len.append(len(toks))
            counts = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            for t in counts:
                self.df[t] = self.df.get(t, 0) + 1
        self.avg_len = (sum(self.doc_len) / self.n) if self.n else 0.0

    def search(self, query, n_results, project_filter=None):
        scores = {}
        for term in set(_tokenize(query)):
            df = self.df.get(term)
            if not df:
                continue
            idf = math.log(1 + (self.n - df + 0.5) / (df + 0.5))
            for i, counts in enumerate(self.tf):
                f = counts.get(term)
                if not f:
                    continue
                denom = f + _K1 * (1 - _B + _B * self.doc_len[i] / self.avg_len)
                scores[i] = scores.get(i, 0.0) + idf * f * (_K1 + 1) / denom
        out = []
        for i, s in sorted(scores.items(), key=lambda kv: -kv[1]):
            rec_id, text, meta = self.records[i]
            if project_filter and (meta or {}).get("project") != project_filter:
                continue
            out.append({"id": rec_id, "text": text, "metadata": meta or {}, "score": 0.0})
            if len(out) >= n_results:
                break
        return out


def _current_index(collection):
    global _cached
    count = collection.count()
    with _lock:
        if _cached and _cached[0] == count and time.time() - _cached[1] < _MAX_AGE_S:
            return _cached[2]
    got = collection.get(include=["documents", "metadatas"])
    idx = _Bm25(list(zip(got["ids"], got["documents"], got["metadatas"])))
    with _lock:
        _cached = (count, time.time(), idx)
    return idx


def hybrid_search(collection, query, n_results=5, project_filter=None):
    """Vector + BM25 retrieval fused with Reciprocal Rank Fusion.

    Returns hits in search_sessions() format plus a "match" field
    ("vector", "keyword", or "keyword+vector"). Keyword-only hits carry
    score 0.0 (no cosine similarity exists for them).
    """
    depth = max(20, n_results)
    try:
        depth = min(depth, max(1, collection.count()))
    except Exception:
        pass

    try:
        vec_hits = search_sessions(collection, query, n_results=depth,
                                   project_filter=project_filter)
    except Exception:
        vec_hits = []
    try:
        kw_hits = _current_index(collection).search(query, depth, project_filter)
    except Exception:
        kw_hits = []

    fused = {}
    for rank, h in enumerate(kw_hits):
        fused[h["id"]] = {"hit": h, "rrf": 1.0 / (_RRF_K + rank + 1), "match": {"keyword"}}
    for rank, h in enumerate(vec_hits):
        f = fused.setdefault(h["id"], {"hit": h, "rrf": 0.0, "match": set()})
        f["rrf"] += 1.0 / (_RRF_K + rank + 1)
        f["match"].add("vector")
        f["hit"] = h  # vector version carries the real similarity score

    best = sorted(fused.values(), key=lambda f: -f["rrf"])[:n_results]
    out = []
    for f in best:
        h = dict(f["hit"])
        h["match"] = "+".join(sorted(f["match"]))
        out.append(h)
    return out
