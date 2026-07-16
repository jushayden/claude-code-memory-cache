# Token-Efficient Claude Code — Principles & Setup

A focused, copy-pasteable guide to making Claude Code (and Claude agents) spend **far fewer tokens per task** — plus the exact tools to install and config to drop in.

> Unofficial. Not affiliated with Anthropic. All paths below are placeholders — swap in your own.

---

## The one idea

**Load on demand, not up front.** Keep the *standing* context (what rides along in every single turn) tiny — names, a compact index, a few rules. Pull the *heavy* stuff — tool schemas, file contents, code structure, past memory — only at the moment it's needed, then let it fall away.

Every technique below is a version of that one idea. The payoff is threefold: **lower cost**, **faster turns** (less to read each time), and **a context window that lasts far longer** before it fills up.

---

## The techniques (mechanism → the win)

### 1. Deferred tool schemas — the biggest single win
MCP servers can expose 100+ tools. If every tool's full JSON schema sits in context at all times, that's **tens of thousands of tokens gone before you type a word**. Modern Claude Code keeps only the tool *names* loaded and fetches a tool's full schema on demand (via ToolSearch) the moment it's actually called.

- **Do:** connect as many MCP servers as you want — their schemas don't all load.
- **Don't:** paste giant tool/API docs into your `CLAUDE.md`; let the harness fetch them just-in-time.
- **Win:** ~30–50k standing tokens saved on a large MCP setup.

### 2. Query a code graph instead of grepping files
Reading files to answer *"what calls X?"* or *"what breaks if I change Y?"* burns thousands of tokens. A pre-built structural graph answers the same question in a handful.

- **Tools:** `graphify` + `code-review-graph` (see the stack below).
- **Setup:** auto-rebuild the graph on every edit (a hook), and add a `CLAUDE.md` rule + a `PreToolUse` nudge so Claude checks the graph *before* Grep/Read.
- **Win:** one graph query ≈ tens of tokens vs. thousands to read several files.

### 3. Progressive-disclosure skills
A "skill" is a folder with a `SKILL.md` and (optionally) heavy data/scripts. The heavy data **never enters context** — only the short `SKILL.md` loads when the skill is triggered, and it queries its data through a script that returns just the answer.

- **Win:** big reference datasets (design systems, style guides, lookup tables) cost ~0 standing tokens.

### 4. Layered memory with a compact index
Don't dump memory into context. Keep a **one-line-per-fact index** that's always loaded; store the full facts in **separate files fetched only when relevant**; use a **local vector store** for semantic recall across sessions.

- **Layout:** `MEMORY.md` (the index) + `memory/<slug>.md` (one fact each) + a vector DB (ChromaDB) for search.
- **Win:** persistent cross-session knowledge at ~one line of context per fact.

### 5. Subagents for fan-out
For broad "search everything" work, dispatch a read-only subagent (e.g. an `Explore` agent). It reads dozens of files but returns **only the conclusion** to your main thread — the file dumps never touch your primary context.

- **Win:** wide investigations without wide context cost.

### 6. Let compaction do its job
When a conversation gets long, Claude Code summarizes older context into a compact form and continues. Don't fight it — structure work so a summary can carry it (clear decisions, explicit state) rather than relying on the full transcript staying in view.

### 7. Push upkeep into hooks
Graph rebuilds, memory embedding, and index refreshes run as **hooks** — background shell commands fired on edit/session events. They keep your queryable stores fresh **without spending main-thread tokens** to do it.

---

## The stack (what to install)

| Tool | Why (token angle) | Install |
|---|---|---|
| **Python 3.10+** | runs the graph + memory tooling | python.org |
| **Node 20+** | runs Claude Code + MCP servers | nodejs.org |
| **graphify** | builds a local code knowledge graph (`graphify-out/`, `GRAPH_REPORT.md`) so you read *structure*, not files | `pip install graphify` *(verify exact package/source)* |
| **code-review-graph** | MCP server exposing graph queries — callers, impact radius, tests-for, semantic search | `pip install code-review-graph` *(verify exact package/source)* |
| **A memory MCP (ChromaDB-backed)** | local vector store for session memory + semantic recall, no API key/cost | ChromaDB via `pip install chromadb`; wire to an MCP server |
| **Obsidian** (optional) | durable notes/session logs the agent can read/write; pairs with a vault MCP | obsidian.md (free) |

> `graphify` and `code-review-graph` are the specific tools this setup uses — confirm the exact package names / repos when you install, since those are the pieces that make "query, don't read" work.

---

## The config (templated — swap in your paths)

### A. Register the MCP servers
Project-scoped in `.mcp.json` (or user-scoped in `~/.claude.json`):

```json
{
  "mcpServers": {
    "code-review-graph": { "command": "code-review-graph", "args": ["serve"], "type": "stdio" },
    "memory": { "command": "python", "args": ["<PATH_TO>/memory_server.py"], "type": "stdio" }
  }
}
```

### B. Hooks — auto-maintain the graph so queries stay cheap
In `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Edit|Write|Bash", "hooks": [
        { "type": "command", "command": "python -c \"from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))\"", "timeout": 30 },
        { "type": "command", "command": "[ -d .git ] && code-review-graph update --skip-flows 2>/dev/null || true", "timeout": 30 }
      ]}
    ],
    "PreToolUse": [
      { "matcher": "Glob|Grep", "hooks": [
        { "type": "command", "command": "[ -f graphify-out/graph.json ] && echo '{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"additionalContext\":\"A code graph exists — read graphify-out/GRAPH_REPORT.md before searching raw files.\"}}' || true" }
      ]}
    ],
    "SessionStart": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "code-review-graph status 2>/dev/null", "timeout": 10 }
      ]}
    ]
  }
}
```

The `PostToolUse` hooks rebuild the graph after each change (so it's always current); the `PreToolUse` hook injects a reminder to use the graph before falling back to raw search.

### C. `CLAUDE.md` rules — the behavioral half
Add this block to your project or global `CLAUDE.md` so the agent actually *uses* the cheap paths:

```markdown
## Token efficiency (follow these)
- BEFORE Grep/Read for "where is X used / impact of changing Y", query the code graph
  (code-review-graph: query_graph, get_impact_radius, semantic_search_nodes).
  Fall back to Grep/Read only if the graph doesn't cover it.
- For architecture questions, read graphify-out/GRAPH_REPORT.md instead of raw files.
- Keep MEMORY.md to one line per fact; store full facts in separate files; recall on demand.
- For broad multi-file searches, dispatch a subagent that returns conclusions, not file dumps.
- Don't paste large docs or tool schemas into context — let ToolSearch / a docs MCP fetch them.
- Prefer editing over re-reading: don't re-read a file you just wrote to "verify" it.
```

---

## Quick-start checklist

1. Install Python 3.10+ and Node 20+.
2. `pip install` graphify + code-review-graph (+ chromadb for memory).
3. Register the MCP servers (section A).
4. Add the hooks to `~/.claude/settings.json` (section B).
5. Add the token-efficiency rules to your `CLAUDE.md` (section C).
6. In each repo: build the graph once (`code-review-graph` build/index; graphify on first edit), then let the hooks keep it fresh.
7. Set up the memory layout: `MEMORY.md` index + `memory/` fact files + the vector store.

That's it. After this, the standing context stays lean (names + a compact index + rules), and the heavy stuff — tool schemas, file contents, code structure, memory — is pulled just-in-time and discarded, instead of riding along in every turn.

## Field-tested additions (from the reference installation)

- **Index your lessons file.** Inject a one-line-per-rule index (~⅓ the tokens);
  read a lesson's full context only when its rule is relevant. (`scripts/` on the
  reference install generates it nightly.)
- **Truncate search results to previews.** `memory_search` returns 500-char
  previews by default with a `full=true` escape hatch — cuts every search ~4×.
- **Fire context nudges once per session, not per tool call.**
- **Curate the store; never bulk-import.** A bulk transcript import once grew the
  reference store to 60% noise and measurably degraded retrieval; the purge halved
  startup search costs and fixed result quality.
