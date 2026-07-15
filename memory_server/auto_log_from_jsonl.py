"""Auto-append new messages from the current Claude Code session to Obsidian.

Runs as a Stop hook (see config/settings.template.json) — after every assistant
turn it reads the session's JSONL transcript from the last-seen byte offset and
appends the new messages to a per-session note in your vault. This is the raw
transcript layer: it works even when the model never calls session_log.

State: memory_server/data/hook_state.json  (session uuid -> offset + note id)
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import SESSIONS_DIR  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

STATE_FILE = Path(__file__).resolve().parent / "data" / "hook_state.json"
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict):
    # atomic: parallel sessions' Stop hooks write this concurrently
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def find_session_jsonl() -> Path | None:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if project_dir and CLAUDE_PROJECTS.exists():
        tail = Path(project_dir).name.lower()
        for c in CLAUDE_PROJECTS.iterdir():
            if c.is_dir() and tail in c.name.lower():
                if session_id and (c / f"{session_id}.jsonl").exists():
                    return c / f"{session_id}.jsonl"
                jsonls = sorted(c.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
                if jsonls:
                    return jsonls[0]
    candidates = [f for p in CLAUDE_PROJECTS.iterdir() if p.is_dir()
                  for f in p.glob("*.jsonl")] if CLAUDE_PROJECTS.exists() else []
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def extract_new_entries(jsonl: Path, start_offset: int):
    entries = []
    end_offset = jsonl.stat().st_size
    if start_offset >= end_offset:
        return entries, end_offset
    with open(jsonl, "rb") as f:
        # Only skip a partial line if genuinely mid-line — saved offsets land on
        # boundaries, and skipping there silently drops the batch's first entry
        if start_offset > 0:
            f.seek(start_offset - 1)
            if f.read(1) != b"\n":
                f.readline()
        else:
            f.seek(0)
        data = f.read().decode("utf-8", errors="replace")
    for line in data.splitlines():
        line = line.strip()
        if not line or len(line) > 200_000:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries, end_offset


def extract_text(entry: dict):
    msg = entry.get("message", {})
    role = msg.get("role") or entry.get("role", "")
    content = msg.get("content") if msg else entry.get("content")
    if not content or role not in ("user", "assistant", "human"):
        return "", "", ""
    texts, actions = [], []
    if isinstance(content, str):
        texts.append(content)
    elif isinstance(content, list):
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                texts.append(b.get("text", ""))
            elif b.get("type") == "tool_use":
                actions.append(f"{b.get('name','')}({str(b.get('input',{}))[:160]})")
    return ("user" if role in ("user", "human") else "assistant",
            "\n".join(texts).strip(), " | ".join(actions).strip())


def main():
    jsonl = find_session_jsonl()
    if not jsonl:
        return
    state = load_state()
    rec = state.get(jsonl.stem)
    if isinstance(rec, int):
        rec = {"offset": rec, "session_id": None}
    elif rec is None:
        rec = {"offset": 0, "session_id": None}

    entries, end = extract_new_entries(jsonl, rec.get("offset", 0))
    if not entries:
        return

    # one note per SESSION: derive the id once, cache it for later turns
    if not rec.get("session_id"):
        topic = "session"
        for e in entries:
            role, text, _ = extract_text(e)
            if role == "user" and text:
                topic = text.strip().split("\n")[0][:50]
                break
        project = Path(os.environ.get("CLAUDE_PROJECT_DIR", "") or "").name or "unknown"
        slug = re.sub(r"[^a-z0-9-]", "-", topic.lower()).strip("-")[:30]
        rec["session_id"] = (f"{datetime.now():%Y-%m-%d}-{project.lower()}"
                             f"-{slug}-{jsonl.stem[:8]}")

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    note = SESSIONS_DIR / f"{rec['session_id']}.md"
    if not note.exists():
        note.write_text(f"---\ndate: {datetime.now():%Y-%m-%d}\nsession_uuid: {jsonl.stem}\n"
                        f"tags:\n  - claude-session\n  - auto-logged\n---\n\n"
                        f"# Claude Session — {rec['session_id']}\n\n---\n", encoding="utf-8")

    chunks = []
    for e in entries:
        role, text, actions = extract_text(e)
        if not role or (not text and not actions):
            continue
        chunk = f"\n### {role.upper()} — {datetime.now():%H:%M:%S}\n\n"
        if text:
            chunk += text[:5000] + ("\n*(...truncated)*" if len(text) > 5000 else "") + "\n"
        if actions:
            chunk += f"\n**Actions:** {actions[:2000]}\n"
        chunks.append(chunk + "\n---\n")
    if chunks:
        with open(note, "a", encoding="utf-8") as f:
            f.write("".join(chunks))

    rec["offset"] = end
    state[jsonl.stem] = rec
    save_state(state)
    print(f"auto-logged {len(chunks)} message(s) -> {note.name}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)  # a logging failure must never crash the Stop hook
