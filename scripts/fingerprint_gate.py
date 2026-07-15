"""Fingerprint gate — skip code-graph rebuilds when code structure didn't change.

Wire this as your PostToolUse hook instead of calling graphify/code-review-graph directly.
Reads the hook payload from stdin, works out which files the tool touched,
fingerprints them (comments + whitespace stripped, then hashed), and only runs
the expensive graph rebuilds when a source file's normalized content actually
changed. Editing markdown, tweaking comments, or reformatting costs ~0.1s
instead of ~0.9s.

State: one JSON per repo under <this repo>/data/fingerprints/ (gitignored).
Override the location with the FPGATE_STATE environment variable.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SOURCE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".lua", ".luau"}
STATE_DIR = Path(os.environ.get(
    "FPGATE_STATE", str(Path(__file__).resolve().parent.parent / "data" / "fingerprints")))
MAX_BASH_FILES = 50

_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_JS = re.compile(r"(?<![:\\])//[^\n]*")     # spare URLs (http://...)
_LINE_PY = re.compile(r"(?m)#[^\n]*$")
_BLOCK_LUA = re.compile(r"--\[\[.*?\]\]", re.DOTALL)
_LINE_LUA = re.compile(r"(?m)--[^\n]*$")


def normalize(text: str, ext: str) -> str:
    if ext == ".py":
        text = _LINE_PY.sub("", text)
    elif ext in (".lua", ".luau"):
        text = _BLOCK_LUA.sub("", text)
        text = _LINE_LUA.sub("", text)
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
        return ([Path(fp)] if fp else []), False
    if tool == "Bash":
        # a shell command may have written anything — ask git what moved
        try:
            r = subprocess.run(["git", "status", "--porcelain"], cwd=str(cwd),
                               capture_output=True, text=True, timeout=8)
            out = []
            for line in r.stdout.splitlines()[:MAX_BASH_FILES]:
                code, p = line[:2], line[3:].strip().strip('"')
                if not p:
                    continue
                # deletes/renames can't be fingerprinted — force a rebuild if
                # the affected path looks like source
                if ("D" in code or "R" in code):
                    tail = p.split(" -> ")[-1].strip().strip('"')
                    if Path(tail).suffix.lower() in SOURCE_EXT or \
                            Path(p.split(" -> ")[0]).suffix.lower() in SOURCE_EXT:
                        return [cwd / tail], True
                out.append(cwd / p)
            return out, False
        except Exception:
            return [], False
    return [], False


def rebuild(cwd: Path):
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

    files, force = touched_files(payload, cwd)
    if force:
        rebuild(cwd)
        print("fpgate: source delete/rename — graphs rebuilt")
        return
    src = []
    for f in files:
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
