"""Tell the agent to read the code graph before it greps raw files.

Claude Code does this with an inline shell conditional in settings.template.json.
That snippet is POSIX-only, so this is the cross-platform equivalent for Codex.

Reads a hook payload on stdin, and if the session's working directory holds a
graphify graph, emits a PreToolUse additionalContext line. Silent otherwise.

    codex_graph_hint.py        (PreToolUse)

Note: whether Codex honours `additionalContext` is not confirmed. If it ignores
the field this is a harmless no-op, and the same instruction is carried by
config/AGENTS.snippet.md, which is the mechanism that definitely works.
"""
import json
import sys
from pathlib import Path

HINT = ("A code graph exists for this project. Read graphify-out/GRAPH_REPORT.md "
        "before searching raw files: it gives callers, dependents and structure "
        "for far fewer tokens than grep.")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}

    cwd = payload.get("cwd") or payload.get("workingDirectory") or "."
    graph = Path(cwd) / "graphify-out" / "graph.json"

    if not graph.exists():
        print("{}")
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": HINT,
        }
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
