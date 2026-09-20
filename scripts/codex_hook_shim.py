"""Bridge Codex hook events to the existing Claude Code hook scripts.

Codex and Claude Code both hand a hook JSON on stdin, but the field names
differ. Rather than fork destructive_guard.py / fingerprint_gate.py, this
translates the Codex payload into the shape they already expect, runs them,
and translates any decision back into Codex's response format.

Usage:
    codex_hook_shim.py --pre     (PreToolUse)
    codex_hook_shim.py --post    (PostToolUse)

Codex's exact field names are not fully documented, so every lookup probes
several plausible keys. The first RAW_LOG_LIMIT payloads are written to
data/codex_hook_payloads.jsonl so the mapping can be corrected against
reality instead of guesswork.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _scripts_dir() -> Path:
    """Where destructive_guard.py and friends live.

    Prefer a real Claude Code install, fall back to this repo's own copy so a
    Codex-only machine still gets the guard instead of silently allowing
    everything.
    """
    override = os.getenv("CLAUDE_SCRIPTS_DIR")
    if override:
        return Path(override)
    installed = Path.home() / ".claude" / "scripts"
    if (installed / "destructive_guard.py").exists():
        return installed
    return REPO / "scripts"


SCRIPTS = _scripts_dir()
PY = os.getenv("MEMORY_PYTHON", sys.executable)
RAW_LOG = REPO / "data" / "codex_hook_payloads.jsonl"
RAW_LOG_LIMIT = 40

SHELL_TOOLS = {"exec", "shell", "bash", "powershell", "run_command", "local_shell"}
EDIT_TOOLS = {"apply_patch", "edit", "write", "write_file", "str_replace", "create_file"}


def first(d: dict, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def log_raw(kind: str, payload: dict):
    try:
        RAW_LOG.parent.mkdir(parents=True, exist_ok=True)
        if RAW_LOG.exists():
            with open(RAW_LOG, "r", encoding="utf-8") as f:
                if sum(1 for _ in f) >= RAW_LOG_LIMIT:
                    return
        # Truncate long VALUES, never the serialized JSON, or the cut can land
        # mid-escape and corrupt the line.
        def clip(v, n=1200):
            if isinstance(v, str):
                return v[:n] + ("..." if len(v) > n else "")
            if isinstance(v, dict):
                return {k: clip(x, n) for k, x in list(v.items())[:20]}
            if isinstance(v, list):
                return [clip(x, n) for x in v[:10]]
            return v
        with open(RAW_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"kind": kind, "payload": clip(payload)}) + "\n")
    except Exception:
        pass


def normalize(payload: dict) -> dict:
    """Map a Codex hook payload onto Claude's {tool_name, tool_input, cwd}."""
    tool = first(payload, "tool_name", "toolName", "name", "tool", default="")
    raw_input = first(payload, "tool_input", "toolInput", "input", "arguments",
                      "parameters", default={})

    if isinstance(raw_input, str):
        try:
            raw_input = json.loads(raw_input)
        except Exception:
            raw_input = {"command": raw_input}
    if not isinstance(raw_input, dict):
        raw_input = {}

    command = first(raw_input, "command", "cmd", "script", "code", "input", default="")
    if isinstance(command, list):
        command = " ".join(str(c) for c in command)

    low = str(tool).lower()
    if low in SHELL_TOOLS:
        claude_tool, tool_input = "Bash", {"command": command}
    elif low in EDIT_TOOLS:
        claude_tool = "Edit"
        tool_input = {"file_path": first(raw_input, "file_path", "path",
                                         "filePath", default="")}
    else:
        claude_tool, tool_input = (str(tool) or "Unknown"), raw_input

    cwd = first(payload, "cwd", "workingDirectory", "working_dir", default=os.getcwd())
    return {"tool_name": claude_tool, "tool_input": tool_input, "cwd": cwd}


def run(script: str, payload: dict, cwd: str) -> tuple[int, str]:
    path = SCRIPTS / script
    if not path.exists():
        return 0, ""
    try:
        p = subprocess.run(
            [PY, str(path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=cwd if os.path.isdir(cwd) else None,
            timeout=45,
        )
        return p.returncode, (p.stdout or "").strip()
    except Exception:
        return 0, ""


def deny(reason: str):
    print(json.dumps({
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }))


def main():
    mode = "--post"
    for a in sys.argv[1:]:
        if a in ("--pre", "--post"):
            mode = a

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        print("{}")
        return

    log_raw(mode, payload)
    norm = normalize(payload)
    cwd = norm["cwd"]

    if mode == "--pre":
        code, out = run("destructive_guard.py", norm, cwd)
        reason = "Blocked by destructive_guard"
        if out:
            try:
                data = json.loads(out)
                hso = data.get("hookSpecificOutput") or {}
                decision = (hso.get("permissionDecision")
                            or data.get("permissionDecision")
                            or data.get("decision"))
                reason = (hso.get("permissionDecisionReason")
                          or data.get("permissionDecisionReason")
                          or data.get("reason") or reason)
                if decision in ("deny", "block"):
                    deny(reason)
                    return
                # destructive_guard returns "ask" for anything it wants a human
                # to approve. Claude Code turns that into a prompt. Codex does
                # not yet support it (openai/codex#28437, still open as of
                # 2026-09-08), and an unrecognized value risks being treated as
                # allow, so fail closed by default.
                #
                # When #28437 ships, set CODEX_HOOK_ALLOW_ASK=1 and this will
                # pass the prompt through natively instead of denying.
                if decision == "ask":
                    if os.environ.get("CODEX_HOOK_ALLOW_ASK") == "1":
                        print(json.dumps({
                            "hookSpecificOutput": {
                                "hookEventName": "PreToolUse",
                                "permissionDecision": "ask",
                                "permissionDecisionReason": reason,
                            }
                        }))
                        return
                    deny(f"{reason} (Claude would prompt here; Codex cannot yet, "
                         f"so this is blocked. Re-run with a narrower, explicit "
                         f"command if intended.)")
                    return
            except Exception:
                pass
        if code == 2:
            deny(reason)
            return
        print("{}")
        return

    run("fingerprint_gate.py", norm, cwd)
    if os.path.isdir(os.path.join(cwd, ".git")):
        try:
            subprocess.run([PY, str(SCRIPTS / "brain_refresh.py")],
                           capture_output=True, cwd=cwd, timeout=90)
        except Exception:
            pass
    print("{}")


if __name__ == "__main__":
    main()
