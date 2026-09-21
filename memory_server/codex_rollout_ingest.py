"""Ingest Codex Desktop rollout transcripts into the shared Obsidian vault.

Mirrors auto_log_from_jsonl.py so Codex sessions land in the same place, in the
same format, and become searchable alongside Claude Code sessions.

Codex rollouts live at:
    ~/.codex/sessions/YYYY/MM/DD/rollout-<ISO>-<session-id>.jsonl

Each line is {timestamp, ordinal, type, payload}. Conversation lives in
type="response_item" with payload.type="message" and a role of user/assistant.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

try:
    from config import SESSIONS_DIR as _SESSIONS_DIR
except Exception:
    # Matches the default in config.example.py, for the case where config.py
    # has not been created yet.
    _SESSIONS_DIR = Path.home() / "ObsidianVault" / "Claude Sessions"

VAULT = Path(os.getenv("MEMORY_SESSIONS_DIR", _SESSIONS_DIR))
STATE_FILE = REPO / "data" / "codex_hook_state.json"
SESSIONS = Path(os.getenv("CODEX_SESSIONS_DIR", Path.home() / ".codex" / "sessions"))

VAULT.mkdir(parents=True, exist_ok=True)
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

SYSTEM_PREFIXES = (
    "<app-context>",
    "<user_instructions>",
    "<recommended_plugins>",
    "<in-app-browser-context",
    "<environment_context>",
)

PROJECT_MAP_FILE = Path(os.getenv("PROJECT_MAP_FILE", REPO / "data" / "project_map.json"))


def load_project_map() -> list:
    """Longest-prefix-first list of (cwd fragment, project name).

    Gitignored, because it is a map of one person's directories. Copy
    config/project_map.example.json to memory_server/data/project_map.json to
    use it. Missing file means fall back to the directory name, which is right
    often enough.
    """
    try:
        pairs = json.loads(PROJECT_MAP_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    return sorted(((str(k).lower(), str(v)) for k, v in pairs.items()),
                  key=lambda kv: len(kv[0]), reverse=True)


PROJECT_MAP = load_project_map()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def newest_rollout() -> Path | None:
    if not SESSIONS.exists():
        return None
    files = list(SESSIONS.rglob("rollout-*.jsonl"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def rollout_session_id(path: Path) -> str:
    """Recover the full session uuid from the filename.

    Filenames look like rollout-<ISO timestamp>-<uuid>.jsonl, and the uuid
    itself contains hyphens, so take the last five hyphen-separated groups.
    """
    parts = path.stem.split("-")
    if len(parts) >= 5:
        return "-".join(parts[-5:])
    return path.stem


def read_lines(path: Path, start_offset: int) -> tuple[list[dict], int]:
    out = []
    with open(path, "rb") as f:
        f.seek(start_offset)
        raw = f.read()
        end = f.tell()
    for line in raw.split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line.decode("utf-8", errors="ignore")))
        except Exception:
            continue
    return out, end


def project_for(cwd: str) -> str:
    low = (cwd or "").lower()
    for needle, name in PROJECT_MAP:
        if needle in low:
            return name
    leaf = Path(cwd).name if cwd else ""
    return leaf or "Codex"


def content_text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
    return "\n".join(parts).strip()


def parse(entries: list[dict]) -> tuple[dict, list[tuple[str, str, str]]]:
    meta = {}
    msgs = []
    for e in entries:
        etype = e.get("type")
        payload = e.get("payload") or {}
        ts = e.get("timestamp", "")

        if etype == "session_meta":
            meta["session_id"] = payload.get("session_id") or payload.get("id") or ""
            meta["cwd"] = payload.get("cwd", "")
            meta["originator"] = payload.get("originator", "Codex")
            meta["timestamp"] = payload.get("timestamp", ts)

        elif etype == "turn_context" and not meta.get("cwd"):
            meta["cwd"] = payload.get("cwd", "")

        elif etype == "response_item" and payload.get("type") == "message":
            role = payload.get("role", "")
            if role not in ("user", "assistant"):
                continue
            text = content_text(payload.get("content"))
            if not text:
                continue
            if text.lstrip().startswith(SYSTEM_PREFIXES):
                continue
            msgs.append((role, text, ts))

    return meta, msgs


def short_topic(msgs) -> str:
    for role, text, _ in msgs:
        if role == "user":
            first = " ".join(text.split())[:60]
            if first:
                return first
    return "Codex session"


def ensure_note(meta: dict, topic: str) -> Path:
    sid = meta.get("session_id", "unknown")
    path = VAULT / f"codex-{sid}.md"
    if path.exists():
        return path
    now = datetime.now()
    fm = f"""---
date: {now.strftime('%Y-%m-%d')}
time: {now.strftime('%H:%M')}
project: {project_for(meta.get('cwd', ''))}
topic: {topic}
session_uuid: {sid}
agent: codex
cwd: {meta.get('cwd', '')}
tags:
  - codex-session
  - auto-logged
---

# Codex Session — {topic}

**Date:** {now.strftime('%B %d, %Y at %I:%M %p')}
**Agent:** {meta.get('originator', 'Codex')}
**Working directory:** `{meta.get('cwd', '')}`

---
"""
    path.write_text(fm, encoding="utf-8")
    return path


def append(path: Path, msgs) -> int:
    if not msgs:
        return 0
    chunks = []
    for role, text, ts in msgs:
        try:
            clock = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
        except Exception:
            clock = datetime.now().strftime("%H:%M:%S")
        icon = "USER" if role == "user" else "ASSISTANT"
        body = text[:5000] + ("\n*(...truncated)*" if len(text) > 5000 else "")
        chunks.append(f"\n### {icon} — {clock}\n\n{body}\n\n---\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write("".join(chunks))
    return len(msgs)


def save_to_memory(meta: dict, msgs, topic: str):
    if len(msgs) < 2:
        return
    try:
        from storage import get_client, get_collection, store_chunk  # type: ignore
    except Exception:
        return
    convo = "\n\n".join(f"{r.upper()}: {t[:1500]}" for r, t, _ in msgs[-8:])
    try:
        col = get_collection(get_client())
        store_chunk(
            col,
            text=f"[Codex session] {topic}\n\n{convo}",
            session_id=f"codex-{meta.get('session_id','')}",
            chunk_type="outcome",
            project=project_for(meta.get("cwd", "")),
            tags=["codex", "auto-logged"],
        )
    except Exception as e:
        print(f"  (chroma save skipped: {e})")


def main():
    target = None

    # A SessionEnd hook hands us the exact transcript on stdin, which beats
    # guessing at the newest file when sessions end close together.
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
            if raw.strip():
                tp = (json.loads(raw) or {}).get("transcript_path")
                if tp:
                    target = Path(tp)
        except Exception:
            pass

    if (target is None or not target.exists()) and len(sys.argv) > 1 \
            and sys.argv[1].endswith(".jsonl"):
        target = Path(sys.argv[1])
    if target is None or not target.exists():
        target = newest_rollout()
    if target is None or not target.exists():
        return

    state = load_state()
    key = str(target)
    offset = state.get(key, {}).get("offset", 0)

    entries, new_offset = read_lines(target, offset)
    if not entries:
        return

    meta, msgs = parse(entries)
    prev = state.get(key, {})
    if not meta.get("session_id"):
        meta["session_id"] = prev.get("session_id") or rollout_session_id(target)
    if not meta.get("cwd"):
        meta["cwd"] = prev.get("cwd", "")

    topic = prev.get("topic") or short_topic(msgs)

    note = ensure_note(meta, topic)
    n = append(note, msgs)
    save_to_memory(meta, msgs, topic)

    state[key] = {
        "offset": new_offset,
        "topic": topic,
        "note": str(note),
        "session_id": meta.get("session_id", ""),
        "cwd": meta.get("cwd", ""),
    }
    save_state(state)
    print(f"codex ingest: +{n} messages -> {note.name}")


if __name__ == "__main__":
    main()
