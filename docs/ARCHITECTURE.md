# Architecture

Claude Brain is five memory layers plus the automation that keeps them fresh. Each layer
answers a different question; together they give the agent continuity and cheap context.

---

## The five layers

### 1. Vector memory — *"have we discussed something like this before?"*
A local **ChromaDB** store of session chunks, exposed through the **memory MCP server**
(`memory_server/server.py`). Built-in embeddings mean it's free and fully local — no API key.
- **Writes:** `memory_save` at meaningful moments; a `Stop` hook can auto-log finished sessions.
- **Reads:** `memory_search` — semantic lookup across every past session.

### 2. File memory — *"the specific facts, cheaply"*
A per-project folder of one-fact-per-file notes with a compact index:
```
<project>/memory/
  MEMORY.md              # one line per fact — the ALWAYS-loaded index
  user_<slug>.md         # who the user is / preferences
  feedback_<slug>.md     # corrections & how-to-apply rules
  project_<slug>.md      # ongoing work, constraints
  reference_<slug>.md    # external pointers
```
Only `MEMORY.md` rides in context every session; full fact files are read **on demand**.

### 3. Obsidian vault — *"the durable narrative"*
Session logs (`Claude Sessions/`), per-project notes (`Projects/<Name>/`), a `Lessons for
Claude.md` (mistakes → rules), a cross-project `Brain Map.md`, and `Home.md` / `About Me.md`.

### 4. Code knowledge graphs — *"where is X used / what breaks if I change Y?"*
`graphify` → `graphify-out/` + `GRAPH_REPORT.md`; `code-review-graph` → an MCP with
`query_graph`, `get_impact_radius`, `semantic_search_nodes`, `detect_changes`. Hooks rebuild
both on every edit so Claude reads **structure, not files**.

### 5. Brain files — *"the single source of truth per project"*
`PROJECT_BRAIN.md` (per repo: stack, conventions, priorities, recently shipped — auto-refresh
sections update on edit) and `Brain Map.md` (the cross-project dashboard).

---

## The automation (hooks)

| Hook event | Runs | Purpose |
|---|---|---|
| `PostToolUse` (Edit/Write/Bash) | rebuild graphs · refresh brain file · embed vault | keep everything current after each change |
| `SessionStart` | graph status · roll up recent sessions | orient at the start |
| `PreToolUse` (Glob/Grep) | inject "read the graph first" reminder | steer to the cheap path |
| `Stop` | log the finished session, file it into the vault | capture the session |

---

## Where does X go? (decision guide)

| You learned… | Put it in… |
|---|---|
| A durable fact about the user/project | **File memory** (`memory/` + a `MEMORY.md` line) |
| A mistake + the rule to avoid repeating it | **`Lessons for Claude.md`** (vault) |
| A searchable summary of a session | **Vector memory** (`memory_save`) + session log |
| Stack/convention/priority for a repo | **`PROJECT_BRAIN.md`** |
| A note for humans to browse | **Obsidian vault** (`Projects/…`) |
| Anything derivable from code/git history | **Nowhere** — don't duplicate it |

---

## Data flow (a session, start to finish)

1. **SessionStart** → hooks report graph status + roll up recent sessions; the agent runs its startup ritual.
2. **During work** → queries the graph before grepping; reads `memory/` facts on demand; saves decisions + logs.
3. **On each edit** → `PostToolUse` hooks rebuild the graph, refresh the brain file, re-embed the vault.
4. **Stop** → the finished session is auto-logged and filed into the vault.

The standing context stays lean; everything heavy is pulled just-in-time.
