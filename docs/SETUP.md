# Setup (manual)

Prefer to let your agent do it? See **[AGENTIC_SETUP.md](AGENTIC_SETUP.md)**. Or just run
`python install.py` from the repo root for a guided setup.

## 0. Prerequisites
- **Python 3.10+** and **Node 20+**
- **Claude Code** (CLI/IDE)
- **Obsidian** (free) — optional but recommended for the vault layer

## 1. Clone + install
```bash
git clone https://github.com/jushayden/claude-code-memory-cache
cd claude-code-memory-cache
pip install -r requirements.txt          # memory server deps (chromadb, mcp)
```

## 2. Install the external tools
```bash
pip install graphify            # code knowledge graph      (verify package/source)
pip install code-review-graph   # graph MCP + query tools   (verify package/source)
```

## 3. Configure paths
```bash
cp memory_server/config.example.py memory_server/config.py
# edit memory_server/config.py — point VAULT_PATH at your Obsidian vault
# (or set MEMORY_CACHE_VAULT / MEMORY_CACHE_CHROMA env vars instead)
```

## 4. Register the MCP servers
Add to your project `.mcp.json` or user `~/.claude.json`:
```json
{
  "mcpServers": {
    "memory":            { "command": "python", "args": ["<MEMORY_CACHE_PATH>/memory_server/server.py"], "type": "stdio" },
    "code-review-graph": { "command": "code-review-graph", "args": ["serve"], "type": "stdio" },
    "obsidian-vault":    { "command": "<your obsidian MCP command>", "type": "stdio" }
  }
}
```

## 5. Add the hooks
Open `config/settings.template.json`, replace `<MEMORY_CACHE_PATH>`, and **merge** the `hooks`
(and, if you like, the minimal `permissions`) into your existing `~/.claude/settings.json`.
Don't blindly overwrite yours. On Windows, swap `2>/dev/null` for `2>NUL` if the hooks error.

## 6. Add the behavioral instructions
Copy `config/CLAUDE.md.template` into your global `~/.claude/CLAUDE.md` (or a project
`CLAUDE.md`) and fill in the `<PLACEHOLDERS>` — your cwd→project map, stack, preferences.

## 7. Seed the vault
Create these at your vault root (empty is fine to start):
```
Home.md              # project index
About Me.md          # who you are / preferences
Lessons for Claude.md
Brain Map.md
Claude Sessions/     # session logs land here
Projects/            # per-project notes
```

## 8. Verify
1. Restart Claude Code so it reloads MCP servers + hooks.
2. Edit a file in a git repo → confirm the code graph updates (PostToolUse hooks firing).
3. In a chat, confirm `memory_search` and `memory_save` work.
4. Start a new session → confirm the SessionStart hook prints graph status.

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for how the layers fit together and
**[TOKEN_EFFICIENCY.md](TOKEN_EFFICIENCY.md)** for the token wins.
