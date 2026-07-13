"""Obsidian vault integration — writes session logs as markdown notes."""

from datetime import datetime
from pathlib import Path
from config import SESSIONS_DIR


def ensure_sessions_dir():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def session_note_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.md"


def create_session_note(session_id: str, project: str = "", topic: str = "") -> Path:
    """Create a new session note with frontmatter."""
    ensure_sessions_dir()
    path = session_note_path(session_id)

    now = datetime.now()
    path.write_text(
        f"---\ndate: {now.strftime('%Y-%m-%d')}\ntime: {now.strftime('%H:%M')}\n"
        f"project: {project}\ntopic: {topic}\ntags:\n  - claude-session\n---\n\n"
        f"# Claude Session — {topic or session_id}\n\n"
        f"**Date:** {now.strftime('%B %d, %Y at %I:%M %p')}\n"
        f"**Project:** {project or 'General'}\n\n---\n\n",
        encoding="utf-8",
    )
    return path


def append_to_session(session_id: str, role: str, content: str, actions: str = ""):
    """Append a message exchange to the running session log."""
    path = session_note_path(session_id)
    if not path.exists():
        create_session_note(session_id)

    now = datetime.now().strftime("%H:%M:%S")
    entry = f"\n### {role.capitalize()} — {now}\n\n{content}\n"
    if actions:
        entry += f"\n**Actions taken:**\n{actions}\n"
    entry += "\n---\n"

    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


def append_summary(session_id: str, summary: str, decisions: list[str]):
    """Append end-of-session summary with key decisions."""
    path = session_note_path(session_id)
    if not path.exists():
        return

    section = f"\n## Session Summary\n\n{summary}\n\n"
    if decisions:
        section += "### Key Decisions\n\n" + "".join(f"- {d}\n" for d in decisions)
    section += "\n"

    with open(path, "a", encoding="utf-8") as f:
        f.write(section)
