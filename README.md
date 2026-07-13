# Claude Code Memory Cache

**Persistent, token-efficient memory for Claude Code.** Give the agent a memory that survives across sessions, projects, and machines — a "cache" for everything it should remember between runs, so it stops forgetting what you told it last week and stops re-reading your whole codebase to answer *"where is X used?"*

> ⚠️ Unofficial. Not affiliated with Anthropic. "Claude" is a trademark of Anthropic; this is an independent community project.

## What it is

Five cooperating memory layers, kept fresh automatically by hooks:

1. **Vector memory** — semantic recall of past sessions (ChromaDB, local, no API cost) → [`memory_server/`](memory_server)
2. **File memory** — a compact `MEMORY.md` index + one-fact-per-file store, read on demand
3. **Obsidian vault** — session logs, per-project notes, a `Lessons` file, a cross-project `Brain Map`
4. **Code knowledge graphs** — `graphify` + `code-review-graph`, so Claude queries *structure* instead of grepping files
5. **Brain files** — a `PROJECT_BRAIN.md` per project, auto-refreshed

The result: continuity across sessions, and much lower token use (see [docs/TOKEN_EFFICIENCY.md](docs/TOKEN_EFFICIENCY.md)).

## Quickstart

```bash
git clone https://github.com/jushayden/claude-code-memory-cache
cd claude-code-memory-cache
pip install -r requirements.txt
python install.py            # guided: deps check, config, snippets to merge, vault seeding
```

Or let your agent do it — paste [docs/AGENTIC_SETUP.md](docs/AGENTIC_SETUP.md) into Claude Code.

## What's in here

```
memory_server/   the memory MCP server (ChromaDB + Obsidian): server.py, storage.py, obsidian.py
config/          CLAUDE.md + settings.json (hooks) templates
docs/            architecture, setup, token efficiency, security
install.py       guided installer
```

## Docs

- **[Architecture](docs/ARCHITECTURE.md)** — the 5 layers + hooks + data flow
- **[Setup](docs/SETUP.md)** — manual install (step by step)
- **[Agentic setup](docs/AGENTIC_SETUP.md)** — let your Claude install it
- **[Token efficiency](docs/TOKEN_EFFICIENCY.md)** — the 7 techniques that cut token use
- **[Security](docs/SECURITY.md)** — scrub checklist before you publish your own setup

## Requirements

Python 3.10+, Node 20+, Claude Code, and (optional but recommended) Obsidian.

## License

MIT — see [LICENSE](LICENSE).
