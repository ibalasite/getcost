#!/usr/bin/env python3
"""
getcost-checkpoint.py — PostToolUse hook: 5-minute cost checkpoint.
Registered in ~/.claude/settings.json PostToolUse event.
Runs with CWD = user's project directory.
Silent exit (0) when interval not yet reached.
"""
import json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("getcost_calc", Path(__file__).parent / "getcost-calc.py")
_mod  = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_mod)
load_config          = _mod.load_config
fetch_exchange_rates = _mod.fetch_exchange_rates
parse_session        = _mod.parse_session
find_newest_jsonl    = _mod.find_newest_jsonl
get_project_hash     = _mod.get_project_hash
format_cost          = _mod.format_cost
fmt_tokens           = _mod.fmt_tokens

def save_json(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)

def ensure_data_dir(cwd: Path) -> Path:
    data_dir = cwd / ".getcost"
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
        (data_dir / ".gitignore").write_text("*\n")
    return data_dir

def main():
    cwd = Path(os.getcwd()).resolve()
    config = load_config()

    interval = int(config.get("checkpoint_interval_minutes", 5))

    data_dir = cwd / ".getcost"
    checkpoint_file = data_dir / "checkpoint.json"

    # Read last reported time
    last_reported = datetime(1970, 1, 1, tzinfo=timezone.utc)
    if checkpoint_file.exists():
        try:
            cp = json.loads(checkpoint_file.read_text())
            ts = cp.get("last_reported_at", "")
            if ts:
                last_reported = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (json.JSONDecodeError, ValueError, OSError):
            pass

    now = datetime.now(timezone.utc)
    elapsed = (now - last_reported).total_seconds() / 60

    if elapsed < interval:
        sys.exit(0)  # silent

    # Interval reached — calculate and report
    project_hash = get_project_hash(str(cwd))
    jsonl = find_newest_jsonl(project_hash)
    if not jsonl:
        sys.exit(0)

    config = fetch_exchange_rates(config)
    sess = parse_session(jsonl)
    tokens = sess["tokens"]
    total_tok = sum(tokens.values())

    ensure_data_dir(cwd)
    save_json(checkpoint_file, {"last_reported_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")})

    print(f"[getcost] ⏱ {interval}min checkpoint — 本 session 累積：{fmt_tokens(total_tok)} tokens → {format_cost(sess['cost_usd'], config)}")

if __name__ == "__main__":
    main()
