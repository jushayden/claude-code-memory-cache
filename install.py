#!/usr/bin/env python3
"""Guided setup for Claude Code Memory Cache.

Does the safe, automatable parts (prereq check, deps, config, vault seeding) and PRINTS the
snippets you merge into your own ~/.claude config — it deliberately does NOT silently edit
your settings.json / CLAUDE.md, since those are personal.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def ok(m):   print(f"  [ok] {m}")
def warn(m): print(f"  [!!] {m}")


def check_versions():
    print("== prerequisites ==")
    v = sys.version_info
    (ok if v >= (3, 10) else warn)(f"python {v.major}.{v.minor}  (need 3.10+)")
    try:
        node = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
        ok(f"node {node}")
    except Exception:
        warn("node not found (need 20+)")


def install_deps():
    print("== dependencies ==")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    print("  also install (verify package/source): pip install graphify code-review-graph")


def seed_vault(vault: Path):
    for f in ["Home.md", "About Me.md", "Lessons for Claude.md", "Brain Map.md"]:
        p = vault / f
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# {f[:-3]}\n", encoding="utf-8")
    (vault / "Claude Sessions").mkdir(parents=True, exist_ok=True)
    (vault / "Projects").mkdir(parents=True, exist_ok=True)
    ok(f"seeded vault at {vault}")


def make_config():
    print("== memory-server config ==")
    cfg = ROOT / "memory_server" / "config.py"
    if cfg.exists():
        ok("memory_server/config.py already exists (leaving it)")
        return
    shutil.copy(ROOT / "memory_server" / "config.example.py", cfg)
    vault = input("  Obsidian vault path (blank to skip the vault layer): ").strip()
    if vault:
        text = cfg.read_text(encoding="utf-8").replace(
            'str(Path.home() / "ObsidianVault")', repr(vault))
        cfg.write_text(text, encoding="utf-8")
        seed_vault(Path(vault))
    ok("created memory_server/config.py")


def print_snippets():
    print("\n== next steps (MERGE into your own ~/.claude — not done automatically) ==")
    print("1. Register MCP servers in ~/.claude.json (see docs/SETUP.md step 4).")
    print(f"     memory server command:  python {ROOT / 'memory_server' / 'server.py'}")
    print("2. Merge hooks from config/settings.template.json into ~/.claude/settings.json")
    print(f"     (replace <MEMORY_CACHE_PATH> with {ROOT})")
    print("3. Append config/CLAUDE.md.template to ~/.claude/CLAUDE.md and fill placeholders.")
    print("4. Restart Claude Code, then verify (docs/SETUP.md step 8).")


if __name__ == "__main__":
    check_versions()
    install_deps()
    make_config()
    print_snippets()
    print("\nDone. Full details in docs/SETUP.md.")
