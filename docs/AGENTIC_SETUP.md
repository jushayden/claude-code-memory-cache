# Agentic setup — let your Claude install it

Claude Code Memory Cache was built *by* an agent, so an agent can install it. Open Claude Code in the
cloned repo and paste the prompt below. It will walk through setup, asking you for your
paths and confirming before it changes anything.

> ⚠️ It will modify `~/.claude/settings.json`, register MCP servers, and create files in
> your vault. Review each step. Nothing here needs `sudo`.

---

## Paste this into Claude Code

```
You are installing "Claude Code Memory Cache" (a persistent memory system) on my machine from this
repo. Work step by step, confirm before each change, and never overwrite my existing
config blindly — merge.

1. Read README.md, docs/ARCHITECTURE.md, and docs/SETUP.md so you understand the layers.
2. Ask me for: my Obsidian vault path (or whether to skip the vault layer), my OS, and the
   absolute path of this repo.
3. Check prerequisites: python --version (need 3.10+), node --version (need 20+). Tell me
   what's missing — don't install runtimes yourself.
4. Install deps: pip install -r requirements.txt, then graphify + code-review-graph. If a
   package name/source is uncertain, ask me rather than guessing.
5. Create memory_server/config.py from memory_server/config.example.py with my real paths.
6. Register the MCP servers (memory, code-review-graph, obsidian-vault) in my ~/.claude.json
   — show me the diff first.
7. Merge the hooks from config/settings.template.json into ~/.claude/settings.json,
   substituting the repo path. Show me the merged result before writing.
8. Append config/CLAUDE.md.template to my ~/.claude/CLAUDE.md and help me fill in the
   placeholders (cwd→project map, stack, preferences).
9. Seed the vault files listed in docs/SETUP.md step 7 if they don't exist.
10. Verify: remind me to restart, then confirm the hooks fire on an edit and memory_search
    works. Report what passed and what didn't.

Stop and ask me whenever a choice is mine to make. Do not commit or push anything.
```

---

If your agent gets stuck on a specific tool (e.g. the exact `graphify` package), fall back
to the manual **[SETUP.md](SETUP.md)** for that step and continue.
