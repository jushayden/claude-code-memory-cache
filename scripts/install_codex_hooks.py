"""Write ~/.codex/hooks.json with paths resolved for this machine.

Reads config/codex_hooks.template.json, substitutes {{PYTHON}} and {{REPO}}, and
writes the result. Backs up any existing hooks.json first.

    python scripts/install_codex_hooks.py            # write it
    python scripts/install_codex_hooks.py --dry-run  # print it instead

Hooks do not fire until they are trusted. After installing, run `codex`, then
`/hooks`, and press t. A handler sitting at Untrusted does nothing, silently.
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TEMPLATE = REPO / "config" / "codex_hooks.template.json"
TARGET = Path.home() / ".codex" / "hooks.json"


def main() -> int:
    dry = "--dry-run" in sys.argv

    if not TEMPLATE.exists():
        print(f"template not found: {TEMPLATE}")
        return 1

    text = TEMPLATE.read_text(encoding="utf-8")
    text = (text
            .replace("{{PYTHON}}", Path(sys.executable).as_posix())
            .replace("{{REPO}}", REPO.as_posix()))
    config = json.loads(text)

    missing = []
    for event, groups in config["hooks"].items():
        for group in groups:
            for handler in group["hooks"]:
                for token in handler["command"].split():
                    if token.endswith(".py") and not Path(token).exists():
                        missing.append(f"{event}: {token}")
    if missing:
        print("refusing to write, these scripts do not exist:")
        for m in missing:
            print("   ", m)
        return 1

    rendered = json.dumps(config, indent=2)
    if dry:
        print(rendered)
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists():
        backup = TARGET.with_suffix(f".json.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(TARGET, backup)
        print(f"backed up existing hooks.json to {backup.name}")

    TARGET.write_text(rendered, encoding="utf-8")
    n = sum(len(g["hooks"]) for gs in config["hooks"].values() for g in gs)
    print(f"wrote {TARGET} ({n} handlers across {len(config['hooks'])} events)")
    print("now run `codex`, then `/hooks`, and press t to trust them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
