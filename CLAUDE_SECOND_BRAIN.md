# Claude Second Brain

A persistent, layered memory system for **Claude Code**. Give Claude a memory that survives across sessions, projects, and machines — so it stops forgetting what you told it last week, and stops burning tokens re-learning your codebase every time.

> ⚠️ **Unofficial.** Not affiliated with Anthropic. "Claude" is a trademark of Anthropic; this is an independent community setup. All paths below are **placeholders** — swap in your own.

---

## 0. The problem (why this exists)

Out of the box, every Claude Code session starts from zero. It doesn't remember past decisions, your preferences, or how your projects fit together — so you re-explain yourself, and it re-reads your whole codebase just to answer *"where is X used?"* Both waste your time and your tokens.

This system fixes that with **five cooperating memory layers**, kept fresh automatically by hooks, plus behavioral rules (in `CLAUDE.md`) that make the agent actually use them.

---

## 1. Architecture — the five layers

### Layer 1 — Vector memory  ·  *"have we discussed something like this before?"*
A local **ChromaDB** store of session chunks, exposed through a small MCP server. Built-in embeddings = free, fully local, no API key. The agent calls `memory_save` at meaningful moments; `memory_search` does semantic lookup across all past work.

### Layer 2 — File memory  ·  *"the specific facts, cheaply"*
A per-project folder of one-fact-per-file notes with a compact index:

```
<project>/memory/
  MEMORY.md            # one LINE per fact — the always-loaded index
  user_<slug>.md       # who the user is / preferences
  feedback_<slug>.md   # corrections + how-to-apply rules
  project_<slug>.md    # ongoing work, constraints
  reference_<slug>.md  # external pointers (URLs, dashboards)
```

Only `MEMORY.md` rides in context every session; full fact files are read **on demand**. Persistent knowledge at ~one line of context each.

### Layer 3 — Obsidian vault  ·  *"the durable narrative"*
A human-readable knowledge base the agent reads/writes:

- `Claude Sessions/` — dated running logs of each session
- `Projects/<Name>/` — per-project overviews, roadmaps, a `Sessions.md` rollup
- `Lessons for Claude.md` — cross-session log of mistakes → rules (read at startup)
- `Brain Map.md` — cross-project dashboard (auto-generated)
- `Home.md` / `About Me.md` — project index + user context

### Layer 4 — Code knowledge graphs  ·  *"where is X used / what breaks if I change Y?"*
Two tools turn your codebase into a queryable graph so Claude reads **structure, not files**:

- **graphify** → `graphify-out/` + `GRAPH_REPORT.md` (god nodes, communities)
- **code-review-graph** → an MCP with `query_graph`, `get_impact_radius`, `semantic_search_nodes`, `detect_changes`, etc.

This is the single biggest token saver for code work (see §7).

### Layer 5 — Brain files  ·  *"the single source of truth per project"*
- `PROJECT_BRAIN.md` (per repo): stack, conventions, priorities, recently shipped. Auto-refresh sections update on every edit; curated sections stay sticky.
- `Brain Map.md` (vault): the cross-project view, rebuilt on session start.

### The automation (hooks)
Layers stay fresh without you thinking about it:

| Hook event | Runs | Purpose |
|---|---|---|
| `PostToolUse` (Edit/Write/Bash) | rebuild graphs · refresh brain file · embed vault | keep everything current after each change |
| `SessionStart` | graph status · roll up recent sessions | orient at the start |
| `PreToolUse` (Glob/Grep) | inject "read the graph first" reminder | steer to the cheap path |
| `Stop` | log the finished session · file it into the vault | capture the session |

### Where does X go? (decision guide)

| You learned… | Put it in… |
|---|---|
| A durable fact about the user/project | **File memory** (`memory/` + a `MEMORY.md` line) |
| A mistake + the rule to avoid repeating it | **`Lessons for Claude.md`** (vault) |
| A searchable summary of a session | **Vector memory** (`memory_save`) + session log |
| Stack/convention/priority for a repo | **`PROJECT_BRAIN.md`** |
| A note for humans to browse | **Obsidian vault** (`Projects/…`) |
| Anything derivable from code/git history | **Nowhere** — don't duplicate it |

---

## 2. What to install

| Tool | Why | Where |
|---|---|---|
| **Python 3.10+** | runs the memory server + tooling | python.org |
| **Node 20+** | runs Claude Code + MCP servers | nodejs.org |
| **Claude Code** | the agent itself | — |
| **Obsidian** (optional) | the vault (free) | obsidian.md |

```bash
pip install chromadb            # local vector store for memory
pip install graphify            # code knowledge graph   (verify package/source)
pip install code-review-graph   # graph MCP + queries    (verify package/source)
```

> `graphify` and `code-review-graph` are the specific tools this setup uses — confirm the exact package names / repos when you install, since those are the pieces that make "query, don't read" work.

---

## 3. The memory server — copy these into files

Create a folder (e.g. `~/claude-brain/memory_server/`) and save these four files.

### `config.py`
```python
# Point the paths at your own locations. Env vars override, so you can leave this
# and set CLAUDE_BRAIN_VAULT / CLAUDE_BRAIN_CHROMA instead.
import os
from pathlib import Path

VAULT_PATH = Path(os.environ.get(
    "CLAUDE_BRAIN_VAULT", str(Path.home() / "ObsidianVault")))
SESSIONS_DIR = VAULT_PATH / "Claude Sessions"

CHROMA_DIR = Path(os.environ.get(
    "CLAUDE_BRAIN_CHROMA",
    str(Path(__file__).resolve().parent / "data" / "chromadb")))

SESSION_COLLECTION = "claude_sessions"
```

### `storage.py`
```python
"""ChromaDB storage for session chunks with built-in embeddings."""
import chromadb
from datetime import datetime
from config import CHROMA_DIR, SESSION_COLLECTION


def get_client() -> chromadb.PersistentClient:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection(client):
    return client.get_or_create_collection(
        name=SESSION_COLLECTION, metadata={"hnsw:space": "cosine"})


def store_chunk(collection, text, session_id, chunk_type, project="", tags=None):
    doc_id = f"{session_id}_{datetime.now().strftime('%H%M%S%f')}"
    metadata = {
        "session_id": session_id, "chunk_type": chunk_type, "project": project,
        "timestamp": datetime.now().isoformat(),
        "tags": ",".join(tags) if tags else "",
    }
    collection.add(documents=[text], metadatas=[metadata], ids=[doc_id])
    return doc_id


def search_sessions(collection, query, n_results=5, project_filter=None):
    where = {"project": project_filter} if project_filter else None
    results = collection.query(
        query_texts=[query], n_results=n_results, where=where,
        include=["documents", "metadatas", "distances"])
    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "id": results["ids"][0][i], "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": 1 - results["distances"][0][i]})
    return hits


def get_session_chunks(collection, session_id):
    results = collection.get(
        where={"session_id": session_id}, include=["documents", "metadatas"])
    return [{"id": results["ids"][i], "text": results["documents"][i],
             "metadata": results["metadatas"][i]}
            for i in range(len(results["ids"]))]
```

### `obsidian.py`
```python
"""Writes session logs as markdown notes into the Obsidian vault."""
from datetime import datetime
from config import SESSIONS_DIR


def session_note_path(session_id):
    return SESSIONS_DIR / f"{session_id}.md"


def create_session_note(session_id, project="", topic=""):
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = session_note_path(session_id)
    now = datetime.now()
    path.write_text(
        f"---\ndate: {now.strftime('%Y-%m-%d')}\nproject: {project}\n"
        f"topic: {topic}\ntags:\n  - claude-session\n---\n\n"
        f"# Claude Session — {topic or session_id}\n\n---\n\n", encoding="utf-8")
    return path


def append_to_session(session_id, role, content, actions=""):
    path = session_note_path(session_id)
    if not path.exists():
        create_session_note(session_id)
    now = datetime.now().strftime("%H:%M:%S")
    entry = f"\n### {role.capitalize()} — {now}\n\n{content}\n"
    if actions:
        entry += f"\n**Actions:**\n{actions}\n"
    entry += "\n---\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


def append_summary(session_id, summary, decisions):
    path = session_note_path(session_id)
    if not path.exists():
        return
    section = f"\n## Session Summary\n\n{summary}\n\n"
    if decisions:
        section += "### Key Decisions\n\n" + "".join(f"- {d}\n" for d in decisions)
    with open(path, "a", encoding="utf-8") as f:
        f.write(section + "\n")
```

### `server.py`
```python
"""MCP server exposing session-memory tools to Claude Code."""
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from storage import (get_client, get_collection, store_chunk,
                     search_sessions, get_session_chunks)
from obsidian import create_session_note, append_to_session, append_summary

mcp = FastMCP("claude-memory")
client = get_client()
collection = get_collection(client)


@mcp.tool()
def memory_search(query: str, n_results: int = 5, project: str = "") -> str:
    """Search past Claude session history for relevant context."""
    hits = search_sessions(collection, query, n_results,
                           project if project else None)
    if not hits:
        return "No relevant past sessions found."
    return "\n\n---\n\n".join(
        f"[{h['metadata'].get('chunk_type','?')}] (score {h['score']:.2f}, "
        f"project {h['metadata'].get('project','N/A')})\n{h['text']}" for h in hits)


@mcp.tool()
def memory_save(text: str, session_id: str, chunk_type: str = "decision",
                project: str = "", tags: str = "") -> str:
    """Save a decision/learning/architecture/preference/outcome. Skip trivia."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    return "Saved: " + store_chunk(collection, text, session_id, chunk_type,
                                   project, tag_list)


@mcp.tool()
def session_start(project: str = "", topic: str = "") -> str:
    """Start a new session log. Call at the beginning of each session."""
    sid = datetime.now().strftime("%Y-%m-%d") + (
        f"-{topic.lower().replace(' ', '-')[:30]}" if topic else "")
    create_session_note(sid, project, topic)
    return f"Session started: {sid}"


@mcp.tool()
def session_log(session_id: str, role: str, content: str, actions: str = "") -> str:
    """Append a message exchange to the running session log."""
    append_to_session(session_id, role, content, actions)
    return f"Logged {role} to {session_id}"


@mcp.tool()
def session_end(session_id: str, summary: str, decisions: str = "") -> str:
    """End a session: save summary + key decisions (pipe-separated)."""
    dl = [d.strip() for d in decisions.split("|") if d.strip()]
    append_summary(session_id, summary, dl)
    if summary:
        store_chunk(collection, summary, session_id, "outcome",
                    tags=["session-summary"])
    for d in dl:
        store_chunk(collection, d, session_id, "decision")
    return f"Session {session_id} ended."


@mcp.tool()
def memory_get_session(session_id: str) -> str:
    """Get all stored chunks from a specific past session."""
    chunks = get_session_chunks(collection, session_id)
    if not chunks:
        return f"No chunks for {session_id}"
    return "\n\n".join(f"[{c['metadata'].get('chunk_type','')}] {c['text']}"
                       for c in chunks)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Install the deps:
```bash
pip install "chromadb>=0.5.0" "mcp>=1.0.0"
```

---

## 4. Configuration

### A) Register the MCP servers
Project `.mcp.json` or user `~/.claude.json`:

```json
{
  "mcpServers": {
    "memory":            { "command": "python", "args": ["<PATH>/memory_server/server.py"], "type": "stdio" },
    "code-review-graph": { "command": "code-review-graph", "args": ["serve"], "type": "stdio" },
    "obsidian-vault":    { "command": "<your obsidian MCP command>", "type": "stdio" }
  }
}
```

### B) Hooks
In `~/.claude/settings.json` — **merge** into yours, don't overwrite. Replace `<CLAUDE_BRAIN_PATH>`. On Windows, swap `2>/dev/null` for `2>NUL` if needed.

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Edit|Write|Bash", "hooks": [
        { "type": "command", "command": "python -c \"from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))\"", "timeout": 30 },
        { "type": "command", "command": "[ -d .git ] && code-review-graph update --skip-flows 2>/dev/null || true", "timeout": 30 }
      ]}
    ],
    "SessionStart": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "code-review-graph status 2>/dev/null || true", "timeout": 10 }
      ]}
    ],
    "PreToolUse": [
      { "matcher": "Glob|Grep", "hooks": [
        { "type": "command", "command": "[ -f graphify-out/graph.json ] && echo '{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"additionalContext\":\"A code graph exists — read graphify-out/GRAPH_REPORT.md before searching raw files.\"}}' || true" }
      ]}
    ]
  }
}
```

### C) `CLAUDE.md` rules — the behavioral half
Add to `~/.claude/CLAUDE.md`:

```markdown
## Startup ritual (every conversation, message 1)
Before responding: run memory_search on the user's first message; read Home.md,
About Me.md, Lessons for Claude.md, and Brain Map.md at the vault root; if in a
known project, read its PROJECT_BRAIN.md.

## Context retrieval — go wide, not deep
Run 3–5 parallel memory_search calls at different angles before saying "I don't
have context." If sparse, Glob + read session logs in the vault.

## Learning from mistakes
Append to Lessons for Claude.md (never overwrite) whenever the user corrects you,
something breaks, you waste a round-trip on info you could have pulled, or you hit a
non-obvious stack fact. Format: Rule / Why (date, project, incident) / Apply.

## Memory during the session
After each substantive response, session_log the exchange. At meaningful moments,
memory_save (decision|learning|architecture|preference|outcome). Skip trivia.
session_end with a summary + key decisions.

## Knowledge graphs — query before you grep
BEFORE Grep/Read for "where is X used / impact of changing Y", query the code graph
(code-review-graph: query_graph, get_impact_radius, semantic_search_nodes). Read
graphify-out/GRAPH_REPORT.md for architecture questions. Fall back to Grep/Read only
when the graph doesn't cover it.

## Token efficiency
Don't paste big docs/tool schemas into context — let ToolSearch fetch on demand.
Keep MEMORY.md to one line per fact; read full fact files on demand. Use a subagent
for broad searches. Don't re-read a file you just wrote.
```

---

## 5. Manual setup

1. Install Python 3.10+ and Node 20+.
2. Save the four `memory_server` files (§3); `pip install chromadb mcp`.
3. `pip install` graphify + code-review-graph.
4. Edit `config.py` → point `VAULT_PATH` at your Obsidian vault.
5. Register the MCP servers (§4A).
6. Merge the hooks into `~/.claude/settings.json` (§4B).
7. Add the `CLAUDE.md` rules (§4C) and fill in your projects/stack.
8. Seed the vault: create `Home.md`, `About Me.md`, `Lessons for Claude.md`, and the folders `Claude Sessions/` and `Projects/`.
9. Restart Claude Code. Verify: edit a file in a git repo (graph updates), and confirm `memory_search` / `memory_save` work in a chat.

---

## 6. Agentic setup — let your Claude install it

Paste this whole document into Claude Code, then add:

```
Install the "Claude Second Brain" system described above on my machine. Work step by
step and confirm before each change; never overwrite my existing config — merge.
First ask me for: my Obsidian vault path, my OS, and where to put the memory_server
folder. Check python/node versions (tell me what to install; don't install runtimes
yourself). Create the four memory_server files, pip install the deps, register the
MCP servers (show me the diff), merge the hooks into ~/.claude/settings.json, append
the CLAUDE.md rules and help me fill in my projects/stack, and seed the vault files.
If a package name/source is uncertain, ask instead of guessing. Do NOT commit or push
anything. Report what passed and what didn't.
```

---

## 7. Token efficiency (why it's cheap)

**The one idea: load on demand, not up front.** Keep the standing context tiny (names, a compact index, a few rules); pull heavy things (tool schemas, file contents, code structure, memory) only when needed, then let them fall away.

1. **Deferred tool schemas** — MCP tool schemas load on demand (ToolSearch), not all at once — saves tens of thousands of standing tokens.
2. **Graph, don't grep** — one graph query answers "who calls X" in a handful of tokens vs. thousands to read files.
3. **Progressive skills** — heavy reference data lives behind a script; only the short `SKILL.md` loads when triggered.
4. **Compact memory index** — `MEMORY.md` = one line/fact; full facts fetched on demand.
5. **Subagents** — fan out reads; the subagent returns the conclusion, not the file dumps.
6. **Compaction** — long chats get summarized; structure work so a summary carries it.
7. **Hooks do upkeep** — graph rebuilds / embeddings run in hooks, not main-thread tokens.

---

## 8. Security / don't-share checklist

This system reads and writes your notes and code. If you ever publish your setup:

**Never share:**
- Your actual Obsidian vault (private notes)
- `.env` / API keys / tokens
- The ChromaDB `data/` folder (contains your session text)
- Your per-project `memory/` fact files
- Your real `~/.claude/settings.json` allow-list (accumulates personal paths and sometimes secrets — share only a minimal template)

**Before publishing,** grep your files for home paths, emails, passwords, and API keys, and replace every hit with a placeholder.

**If you commit a secret:** rotate it immediately (assume compromised), then scrub git history. Rotation is the only real fix.
