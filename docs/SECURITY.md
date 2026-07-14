# Security & Privacy

Claude Code Memory Cache reads and writes your notes, code, and memory. That means a repo can easily
pick up personal data if you're not careful. Read this before you push anything public.

## Never commit these
The included `.gitignore` blocks them, but double-check:
- **`.env` / API keys / tokens**
- **Your actual Obsidian vault** — it's your private notes. Ship *examples*, never the real vault.
- **`data/` and ChromaDB stores** — they contain the text of your sessions.
- **`memory/` fact files** — per-project facts about you and your work are personal.

## Before you make a repo public — scrub checklist
Search the whole repo and replace every hit with a placeholder:
- Absolute home paths (Windows, macOS, Linux)
- Email addresses and real names
- Client / employer / project names you don't want public
- Secrets in permission allow-lists (e.g. a DB password baked into a `Bash(...)` rule)
- Hostnames / IPs / tunnel URLs
- API keys hardcoded in any script (they should read from env, not literals)

A quick sweep (run at the repo root, review every hit):
```bash
grep -rIn -e "Users" -e "/home/" -e "@gmail" -e "-p" -e "sk-" -e "api_key" -e "Bearer " . \
  --exclude-dir=.git
```

## Your `settings.json` allow-list is not a template
A real, long-lived `~/.claude/settings.json` accumulates hundreds of one-off `allow` rules —
many with personal paths and sometimes secrets. **That file is not shareable.** Ship the
minimal, generic `config/settings.template.json` and let each user grow their own.

## If you accidentally commit a secret
1. **Rotate it immediately** — assume it's compromised the moment it's pushed.
2. Remove it from history (`git filter-branch` / BFG), then force-push.
3. Git history is forever on forks/clones — rotation is the only real fix.
