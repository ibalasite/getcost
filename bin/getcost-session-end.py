#!/usr/bin/env python3
"""
getcost-session-end.py — Stop hook: session-end accounting.
Registered in ~/.claude/settings.json Stop event.
Runs with CWD = user's project directory.
"""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("getcost_calc", Path(__file__).parent / "getcost-calc.py")
_mod  = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_mod)
load_config        = _mod.load_config
fetch_exchange_rates = _mod.fetch_exchange_rates
parse_session      = _mod.parse_session
find_newest_jsonl  = _mod.find_newest_jsonl
get_project_hash   = _mod.get_project_hash
format_cost        = _mod.format_cost
fmt_tokens         = _mod.fmt_tokens

def ensure_data_dir(cwd: Path) -> Path:
    data_dir = cwd / ".getcost"
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
        (data_dir / ".gitignore").write_text("*\n")
    return data_dir

def load_sessions(sessions_file: Path, cwd: Path) -> dict:
    if sessions_file.exists():
        try:
            return json.loads(sessions_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"project_path": str(cwd), "project_total": {
        "input_tokens": 0, "cache_write_tokens": 0,
        "cache_read_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
    }, "sessions": []}

def save_json(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)

def main():
    cwd = Path(os.getcwd()).resolve()
    config = load_config()
    config = fetch_exchange_rates(config)

    project_hash = get_project_hash(str(cwd))
    jsonl = find_newest_jsonl(project_hash)
    if not jsonl:
        return  # no session data — silent exit

    sess = parse_session(jsonl)
    tokens = sess["tokens"]
    cost_usd = sess["cost_usd"]

    # Determine primary model used
    model = max(sess["model_breakdown"], key=lambda m: sess["model_breakdown"][m].get("output", 0), default="unknown")

    # Lazy-create data directory
    data_dir = ensure_data_dir(cwd)
    sessions_file = data_dir / "sessions.json"

    # Load existing data
    data = load_sessions(sessions_file, cwd)

    # Append session record
    record = {
        "session_id": sess["session_id"],
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": model,
        "tokens": {
            "input":       tokens["input"],
            "cache_write": tokens["cache_write"],
            "cache_read":  tokens["cache_read"],
            "output":      tokens["output"],
        },
        "cost_usd": cost_usd,
    }
    data["sessions"].append(record)

    # Update project total
    pt = data["project_total"]
    pt["input_tokens"]       = pt.get("input_tokens", 0)       + tokens["input"]
    pt["cache_write_tokens"] = pt.get("cache_write_tokens", 0) + tokens["cache_write"]
    pt["cache_read_tokens"]  = pt.get("cache_read_tokens", 0)  + tokens["cache_read"]
    pt["output_tokens"]      = pt.get("output_tokens", 0)      + tokens["output"]
    pt["cost_usd"]           = round(pt.get("cost_usd", 0.0)   + cost_usd, 6)

    save_json(sessions_file, data)

    # Reset checkpoint (next session starts fresh)
    checkpoint_file = data_dir / "checkpoint.json"
    save_json(checkpoint_file, {"last_reported_at": "1970-01-01T00:00:00Z"})

    # Print summary
    session_count = len(data["sessions"])
    total_tok = sum(pt.get(k, 0) for k in ("input_tokens", "cache_write_tokens", "cache_read_tokens", "output_tokens"))
    session_tok = sum(tokens.values())

    print()
    print("[getcost] Session 結束 " + "─" * 26)
    print(f"  本次：{fmt_tokens(session_tok)} tokens → {format_cost(cost_usd, config)}")
    print(f"  目錄累積（{session_count} sessions）：{fmt_tokens(total_tok)} tokens → {format_cost(pt['cost_usd'], config)}")
    print("─" * 45)

if __name__ == "__main__":
    main()
