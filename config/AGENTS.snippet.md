# AGENTS.md snippet

Paste this into `~/.codex/AGENTS.md`. Codex reads that file at session start. Without it, a Codex
session has no idea the memory system exists.

This is only the memory half. Anything else you want Codex to know (project layout, house style,
constraints) goes in the same file alongside it.

---

## Shared memory system

You share a persistent memory store with Claude Code sessions. Nothing is injected automatically,
so the startup ritual below is mandatory.

### Startup ritual (every session, before responding)

1. **Read the memory index** for the active project:
   `~/.claude/projects/<slug>/memory/MEMORY.md`
   One line per fact. Open individual fact files only when a line looks relevant.
2. **Call `memory_search`** with the user's first message as the query. This hits a shared store
   written by every session across both tools.
3. **Read `PROJECT_BRAIN.md`** at the project root if it exists. Stack, conventions, priorities,
   recent commits.

Memory directories are slugged from the project's absolute path, lowercased with separators
replaced by hyphens (`C:\Work\my-app` becomes `c--Work-my-app`).

### Retrieval: targeted first, wide when it matters

Start with 1-2 targeted `memory_search` calls. Escalate to 3-5 parallel searches whenever:

- The question is about past work or continuity ("what did we...", "where were we")
- The first search returns thin or irrelevant results
- The user references something you do not recognize

Vary the angle on the wide pass: literal query, project name, related keywords, recent work, stack
terms. Results are 500-character previews, so re-search with `full=true` when a relevant one is cut
off.

If memory is still thin, glob the vault's session-log folder for matching notes before saying you
lack context. "Not enough info" is almost always a failure to search widely enough.

### Prefer the code graph over grepping

If `graphify-out/` exists in the project, read `graphify-out/GRAPH_REPORT.md` before searching raw
files. It gives you callers, dependents and structure for far fewer tokens than grep does. Claude
Code gets this as an automatic reminder on every search; you have to remember it yourself.

### Saving memory

Call `memory_save` after decisions, architectural choices, learnings, and stated preferences. Skip
acknowledgements ("ok", "push it", "looks good").

- SAVE: "Chose indigo over cyan for the hero accent"
- SAVE: "Combat resolution runs on a 5Hz server tick"
- SKIP: confirmations

Durable facts that future sessions must not re-derive belong in a fact file under the project's
`memory/` directory, **plus a one-line pointer in `MEMORY.md`**. A fact file with no index line is
unreachable.

### Parity with Claude Code

You run hooks through `~/.codex/hooks.json`:

- `SessionStart` reports whether this repo's code graph is stale.
- `PostToolUse` rebuilds the code graph in git repos, skipping non-structural edits.
- `SessionEnd` writes your transcript into the shared session-log folder.

Memories you save are visible to Claude sessions immediately, and the reverse is also true.

If you have added a `PreToolUse` handler with your own safety guard, one difference matters. A guard
decision of `ask` means a human should approve. Claude Code turns that into a prompt; Codex cannot
yet ([openai/codex#28437](https://github.com/openai/codex/issues/28437)), so the shim fails closed
and denies. If a legitimate command is blocked, rerun it as a narrower explicit command rather than
routing around the guard.
