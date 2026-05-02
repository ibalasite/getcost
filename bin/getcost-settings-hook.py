#!/usr/bin/env python3
"""
getcost-settings-hook.py — manage Stop + PostToolUse hooks in ~/.claude/settings.json.

Subcommands:
  add-stop          inject Stop hook
  add-posttooluse   inject PostToolUse hook
  remove            remove all getcost hooks
  init-config       create ~/.getcost/config.json with defaults
"""
import json, os, sys, tempfile
from pathlib import Path

SETTINGS = Path.home() / ".claude" / "settings.json"
CONFIG   = Path.home() / ".getcost" / "config.json"
RUNTIME  = Path.home() / ".claude" / "skills" / "getcost"
MARKER   = "getcost"

STOP_CMD        = f'python3 "{RUNTIME}/bin/getcost-session-end.py"'
POSTTOOLUSE_CMD = f'python3 "{RUNTIME}/bin/getcost-checkpoint.py"'

DEFAULT_CONFIG = {
    "checkpoint_interval_minutes": 5,
    "exchange_rates": {},
    "exchange_rates_updated": None,
}


def load_settings() -> dict:
    if SETTINGS.exists():
        try:
            return json.loads(SETTINGS.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}

def save_settings(data: dict):
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=SETTINGS.parent, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, str(SETTINGS))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    print(f"[getcost-hook] settings.json updated")


def _hook_exists(entries: list, command: str) -> bool:
    for entry in entries:
        for h in entry.get("hooks", []):
            if MARKER in h.get("command", ""):
                return True
    return False

def add_hook(event: str, command: str, matcher: str = None):
    data = load_settings()
    hooks = data.setdefault("hooks", {})
    entries = hooks.setdefault(event, [])

    if _hook_exists(entries, command):
        print(f"[getcost-hook] {event} hook already present, skipping")
        return

    hook_obj = {"type": "command", "command": command}
    entry = {"hooks": [hook_obj]}
    if matcher:
        entry["matcher"] = matcher
    entries.append(entry)

    save_settings(data)
    print(f"[getcost-hook] {event} hook registered")

def remove_hooks():
    data = load_settings()
    changed = False

    for event, entries in list(data.get("hooks", {}).items()):
        new_entries = []
        for entry in entries:
            kept = [h for h in entry.get("hooks", []) if MARKER not in h.get("command", "")]
            if kept:
                entry["hooks"] = kept
                new_entries.append(entry)
            else:
                changed = True
        data["hooks"][event] = new_entries
        if not new_entries:
            del data["hooks"][event]
            changed = True

    if not data.get("hooks"):
        data.pop("hooks", None)

    if changed:
        save_settings(data)
        print("[getcost-hook] hooks removed")
    else:
        print("[getcost-hook] no getcost hooks found")

def init_config():
    if CONFIG.exists():
        print(f"[getcost-hook] config already exists: {CONFIG}")
        return
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=CONFIG.parent, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        os.replace(tmp, str(CONFIG))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    print(f"[getcost-hook] config initialised: {CONFIG}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "add-stop":
        add_hook("Stop", STOP_CMD)
    elif cmd == "add-posttooluse":
        add_hook("PostToolUse", POSTTOOLUSE_CMD, matcher=".*")
    elif cmd == "remove":
        remove_hooks()
    elif cmd == "init-config":
        init_config()
    else:
        print(f"Usage: {sys.argv[0]} add-stop | add-posttooluse | remove | init-config")
        sys.exit(1)
