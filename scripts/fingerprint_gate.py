"""Fingerprint gate — skip code-graph rebuilds when code structure didn't change.

Wire this as your PostToolUse hook instead of calling graphify/code-review-graph
directly (see config/settings.template.json). It reads the hook payload from
stdin, works out which files the tool touched, fingerprints them (comments and
whitespace stripped, then hashed), and only runs the expensive graph rebuilds
when a source file's normalized content actually changed.

Result: editing markdown, tweaking comments, or reformatting costs ~0.1s
instead of ~0.9s per edit. Measured on a real installation — see docs/STATS.md.

State: JSON per repo under <this repo>/data/fingerprints/ (gitignored).
Override the location with the FPGATE_STATE environment variable.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SOURCE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
STATE_DIR = Path(os.environ.get(
    "FPGATE_STATE", str(Path(__file__).resolve().parent.parent / "data" / "fingerprints")))
MAX_BASH_FILES = 50

_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_JS = re.compile(r"(?<![:\\])//[^\n]*")     # spares URLs (http://...)
_LINE_PY = re.compile(r"(?m)#[^\n]*$")


def normalize(text: str, ext: str) -> str:
    if ext == ".py":
        text = _LINE_PY.sub("", text)
    else:
        text = _BLOCK.sub("", text)
        text = _LINE_JS.sub("", text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return hashlib.sha256("\n".join(lines).encode("utf-8", "replace")).hexdigest()[:16]


def touched_files(payload: dict, cwd: Path):
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}
    if tool in ("Edit", "Write", "NotebookEdit"):
        fp = ti.get("file_path") or ti.get("notebook_path") or ""
        return [Path(fp)] if fp else []
    if tool == "Bash":
        # a shell command may have written anything — ask git what moved
        try:
            r = subprocess.run(["git", "status", "--porcelain"], cwd=str(cwd),
                               capture_output=True, text=True, timeout=8)
            return [cwd / line[3:].strip().strip('"')
                    for line in r.stdout.splitlines()[:MAX_BASH_FILES] if line[3:].strip()]
        except Exception:
            return []
    return []


def rebuild(cwd: Path):
    """Run whichever graph tools are installed; silently skip the rest."""
    try:
        from graphify.watch import _rebuild_code
        _rebuild_code(cwd)
    except Exception:
        pass
    try:
        subprocess.run(["code-review-graph", "update", "--skip-flows"],
                       cwd=str(cwd), capture_output=True, timeout=60)
    except Exception:
        pass


def main():
    cwd = Path.cwd()
    if not (cwd / ".git").is_dir():
        return
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    src = []
    for f in touched_files(payload, cwd):
        try:
            f = f.resolve()
            if f.suffix.lower() in SOURCE_EXT and f.is_file() \
                    and str(f).lower().startswith(str(cwd.resolve()).lower()):
                src.append(f)
        except OSError:
            continue
    if not src:
        print("fpgate: no source files touched — graph rebuild skipped")
        return

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(str(cwd.resolve()).lower().encode()).hexdigest()[:12]
    state_file = STATE_DIR / f"{key}.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        state = {}

    changed = False
    for f in src:
        try:
            h = normalize(f.read_text(encoding="utf-8", errors="replace"), f.suffix.lower())
        except OSError:
            continue
        k = str(f).lower()
        if state.get(k) != h:
            state[k] = h
            changed = True

    if changed:
        rebuild(cwd)
        state_file.write_text(json.dumps(state), encoding="utf-8")
        print(f"fpgate: structural change in {len(src)} file(s) — graphs rebuilt")
    else:
        print("fpgate: comment/format-only change — graph rebuild skipped")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)  # never block the session on gate failure
