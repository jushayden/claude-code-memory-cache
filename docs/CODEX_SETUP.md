# Wiring Codex into the memory cache

**Audience: a Codex agent.** If a human hands you this file, your job is to wire the Codex on this
machine into the memory system in this repo. Work out the local paths yourself, then verify. Do not
ask the human for a path you can discover.

Claude Code and Codex end up as two clients of one store, so a session in either tool can search
what the other one did.

## What the system is

```
Codex session                     Claude Code session
     |                                    |
     |  MCP (memory_server/server.py)     |  MCP
     |  hooks (~/.codex/hooks.json)       |  hooks (settings.json)
     v                                    v
     +--------- vector store -------------+     shared memory
     |                                    |
     +--------- notes vault --------------+     shared transcripts
```

- **The store** is ChromaDB. If you run `memory_server/chroma_service.py`, every client talks to one
  HTTP service rather than opening the database directly. Several processes opening it directly will
  corrupt the index.
- **The MCP server** (`memory_server/server.py`) gives Codex `memory_search` and `memory_save`.
- **The hooks** run scripts at session and tool boundaries. They are what make memory automatic
  instead of something the agent has to remember to do.
- **The vault** is a plain notes directory. Session transcripts land there and are searchable by
  both tools.

## Where things live

General areas, not exact paths. Resolve each on the machine you are running on.

| What | Where to look | How to confirm |
|---|---|---|
| This repo | Wherever it was cloned | The directory holding `install.py` and `memory_server/` |
| Your config | `memory_server/config.py` | Copy `config.example.py` if it does not exist yet |
| Codex config | `~/.codex/` | `config.toml`, `hooks.json`, `AGENTS.md` all live here |
| Codex transcripts | `~/.codex/sessions/YYYY/MM/DD/` | Files named `rollout-<ISO>-<uuid>.jsonl` |
| The notes vault | `VAULT_PATH` in `memory_server/config.py` | Read the file, do not guess |
| Python interpreter | The one with `requirements.txt` installed | Must import `chromadb` and `mcp`. The bare `python` on PATH is often the wrong one on Windows |

## What has to be true

**1. Dependencies installed.** `pip install -r requirements.txt` against the interpreter you intend
to use. Confirm with an actual import of `chromadb`, not by reading the file.

**2. Config exists.** `memory_server/config.py`, copied from `config.example.py`, with `VAULT_PATH`
pointing at a real directory.

**3. Codex knows about the MCP.** An `[mcp_servers.claude-memory]` block in `~/.codex/config.toml`
pointing an absolute interpreter path at `memory_server/server.py`. Confirm with `codex mcp list`.

```toml
[mcp_servers.claude-memory]
command = '/absolute/path/to/python'
args = ['/absolute/path/to/this/repo/memory_server/server.py']
```

Put API keys in environment variables, never in `[mcp_servers.*.env]` tables.

**4. Hooks are installed AND trusted.** Two separate conditions, and the second is the one people
miss.

Run `python scripts/install_codex_hooks.py`. It fills the template with this machine's interpreter
and repo paths, backs up any existing `hooks.json`, and refuses to write if a referenced script is
missing.

Then trust them. Hooks do not fire until approved, and approval only works from the **CLI**, not
Desktop:

```
codex
/hooks        -> press t
```

Every handler must read `Active`. One sitting at `Untrusted` does nothing, silently.

### Do not hand-write hooks.json

The schema nests three levels deep, and a wrong shape parses fine and never fires:

```json
{ "hooks": { "<Event>": [ { "matcher": "...", "hooks": [ { "type": "command", "command": "..." } ] } ] } }
```

A flat `{"hooks": {"PreToolUse": [{"command": "..."}]}}` looks right and does nothing. Use the
installer.

## What each hook is for

| Event | Runs | Why |
|---|---|---|
| `PostToolUse` | `scripts/codex_hook_shim.py --post` | Refreshes the code graph, skipping non-structural edits via `fingerprint_gate.py` |
| `SessionEnd` | `memory_server/codex_rollout_ingest.py` | Writes the transcript into the vault and the vector store |

`SessionEnd` is the one that makes memory work. `PostToolUse` keeps the code graph current and is
optional.

The shim exists because Codex and Claude Code pass hook payloads with different field names. It
translates, calls the script unchanged, and translates the result back.

### The safety guard is not included

`codex_hook_shim.py` also supports `--pre`, which forwards to a `destructive_guard.py` that this
repo does not ship. If you have one in `~/.claude/scripts/`, the shim will find and use it, and you
can add a `PreToolUse` handler yourself. Without that script, leave `PreToolUse` out rather than
wiring a handler that silently allows everything.

## Verify

Do not wait for a session. Test directly.

```
echo '{"tool_name":"shell","tool_input":{"command":"git status"},"cwd":"/tmp"}' | <python> scripts/codex_hook_shim.py --post
```

It should exit cleanly. Then:

- `data/codex_hook_payloads.jsonl` logs the first 40 hook payloads. If it only holds your own test
  invocations, the hooks are installed but not trusted.
- End a Codex session and confirm a new note appeared in the vault's session folder.
- Ask for something only a Claude Code session wrote. If `memory_search` returns it, the store is
  genuinely shared.

## Tunables

All optional; defaults are correct for a normal install.

| Variable | Default | Used by |
|---|---|---|
| `CLAUDE_SCRIPTS_DIR` | `~/.claude/scripts`, then this repo's `scripts/` | `codex_hook_shim.py` |
| `MEMORY_PYTHON` | the running interpreter | `codex_hook_shim.py` |
| `MEMORY_SESSIONS_DIR` | `SESSIONS_DIR` from `config.py` | `codex_rollout_ingest.py` |
| `CODEX_SESSIONS_DIR` | `~/.codex/sessions` | `codex_rollout_ingest.py` |
| `PROJECT_MAP_FILE` | `memory_server/data/project_map.json` | `codex_rollout_ingest.py` |
| `CODEX_HOOK_ALLOW_ASK` | unset | `codex_hook_shim.py`, see below |

## Known gaps

**A guard decision of `ask` cannot prompt.** Claude Code turns `ask` into a prompt. Codex cannot
([openai/codex#28437](https://github.com/openai/codex/issues/28437)), so the shim fails closed and
denies. When that ships, set `CODEX_HOOK_ALLOW_ASK=1`.

**Incremental reads lack `session_meta`.** `codex_rollout_ingest.py` recovers the session id from
the rollout filename and persists it. Without that, one session splits across two vault notes.

**Codex keeps its own `memories_1.sqlite`.** Separate from ChromaDB and currently dormant. Worth
watching in case Codex starts writing memories the shared store never sees.

**Transcripts are tagged with a project name.** The ingester matches the session working directory
against `memory_server/data/project_map.json`, longest key first. That file is gitignored, so the
repo ships nobody's directory layout. Without it, the ingester falls back to the working directory's
name, which is usually good enough.

## Also do this

Paste `config/AGENTS.snippet.md` into `~/.codex/AGENTS.md`, fixing the paths for this machine. Codex
reads that file at session start. Hooks make memory automatic; the snippet is what makes the agent
actually search before it answers.
