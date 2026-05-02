#!/usr/bin/env python3
from __future__ import annotations
"""
getcost-calc.py — core token cost library + CLI.

CLI modes:
  python3 getcost-calc.py --session <file>   # parse one JSONL, print summary
  python3 getcost-calc.py --report           # full report for current directory
"""
import argparse, json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

# ── Pricing table (USD per 1M tokens) ────────────────────────────────────────
PRICING = {
    "claude-opus-4-7":          {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
    "claude-sonnet-4-6":        {"input":  3.00, "output": 15.00, "cache_write":  3.75, "cache_read": 0.30},
    "claude-haiku-4-5":         {"input":  0.80, "output":  4.00, "cache_write":  1.00, "cache_read": 0.08},
    "claude-haiku-4-5-20251001":{"input":  0.80, "output":  4.00, "cache_write":  1.00, "cache_read": 0.08},
    "_default":                 {"input":  3.00, "output": 15.00, "cache_write":  3.75, "cache_read": 0.30},
}

# ── Locale → currency ─────────────────────────────────────────────────────────
LOCALE_CURRENCY = [
    ("zh_TW", "TWD", "NT$"),
    ("zh_HK", "HKD", "HK$"),
    ("zh",    "TWD", "NT$"),  # generic zh → TWD
    ("ja",    "JPY",  "¥"),
    ("ko",    "KRW",  "₩"),
    ("de",    "EUR",  "€"),
    ("fr",    "EUR",  "€"),
    ("es",    "EUR",  "€"),
    ("it",    "EUR",  "€"),
    ("pt",    "EUR",  "€"),
    ("en",    "USD",  "$"),
]

CONFIG_PATH = Path.home() / ".getcost" / "config.json"
PROJECTS_DIR = Path.home() / ".claude" / "projects"
RATE_TTL_HOURS = 24


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}

def save_config(data: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(CONFIG_PATH)

def init_config():
    """Create default config if not present."""
    if CONFIG_PATH.exists():
        return
    save_config({
        "checkpoint_interval_minutes": 5,
        "exchange_rates": {},
        "exchange_rates_updated": None,
    })


# ── Exchange rates ─────────────────────────────────────────────────────────────

def _rates_stale(config: dict) -> bool:
    updated = config.get("exchange_rates_updated")
    if not updated:
        return True
    try:
        ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - ts > timedelta(hours=RATE_TTL_HOURS)
    except (ValueError, TypeError):
        return True

def fetch_exchange_rates(config: dict, force: bool = False) -> dict:
    if not force and not _rates_stale(config):
        return config
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        if data.get("result") == "success":
            config["exchange_rates"] = data["rates"]
            config["exchange_rates_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            save_config(config)
    except Exception:
        pass  # use cached rates if fetch fails
    return config


# ── Currency detection ─────────────────────────────────────────────────────────

def detect_currency(config: dict) -> tuple[str, str, float]:
    """Return (currency_code, symbol, rate_from_usd)."""
    preferred = config.get("preferred_currency")
    if not preferred:
        for env_var in ("LC_MONETARY", "LANG", "LC_ALL"):
            locale = os.environ.get(env_var, "")
            for prefix, code, symbol in LOCALE_CURRENCY:
                if locale.startswith(prefix):
                    preferred = code
                    break
            if preferred:
                break

    if not preferred or preferred == "USD":
        return "USD", "$", 1.0

    rates = config.get("exchange_rates", {})
    rate = rates.get(preferred)
    if not rate:
        return "USD", "$", 1.0

    # find symbol
    symbol = preferred  # fallback
    for _, code, sym in LOCALE_CURRENCY:
        if code == preferred:
            symbol = sym
            break

    return preferred, symbol, float(rate)


# ── Token parsing ─────────────────────────────────────────────────────────────

def parse_session(path) -> dict:
    """
    Parse a JSONL session file. Deduplicate by message.id.
    Returns:
      {
        'tokens': {'input': int, 'cache_write': int, 'cache_read': int, 'output': int},
        'cost_usd': float,
        'session_id': str,          # filename stem
        'model_breakdown': {model: {tokens..., cost_usd: float}},
      }
    """
    path = Path(path)
    tokens_by_model = defaultdict(lambda: {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0})
    seen_ids = set()

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = obj.get("message") or {}
                usage = msg.get("usage")
                msg_id = msg.get("id")
                if not usage or not msg_id:
                    continue
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)

                model = msg.get("model") or "_default"
                # normalise model key: prefix-match against PRICING
                pricing_key = "_default"
                for key in PRICING:
                    if key == "_default":
                        continue
                    if model.startswith(key) or key.startswith(model.split("-20")[0]):
                        pricing_key = key
                        break
                if pricing_key == "_default" and model in PRICING:
                    pricing_key = model

                tm = tokens_by_model[pricing_key]
                tm["input"]       += usage.get("input_tokens", 0)
                tm["cache_write"] += usage.get("cache_creation_input_tokens", 0)
                tm["cache_read"]  += usage.get("cache_read_input_tokens", 0)
                tm["output"]      += usage.get("output_tokens", 0)

    except OSError:
        pass

    # Calculate costs
    total = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
    total_cost = 0.0
    breakdown = {}

    for model, tm in tokens_by_model.items():
        p = PRICING.get(model, PRICING["_default"])
        cost = (
            tm["input"]       * p["input"]       / 1_000_000 +
            tm["cache_write"] * p["cache_write"]  / 1_000_000 +
            tm["cache_read"]  * p["cache_read"]   / 1_000_000 +
            tm["output"]      * p["output"]       / 1_000_000
        )
        breakdown[model] = {**tm, "cost_usd": round(cost, 6)}
        total_cost += cost
        for k in total:
            total[k] += tm[k]

    return {
        "tokens": total,
        "cost_usd": round(total_cost, 6),
        "session_id": path.stem,
        "model_breakdown": breakdown,
    }


# ── Formatting ─────────────────────────────────────────────────────────────────

def format_cost(usd: float, config: dict) -> str:
    code, symbol, rate = detect_currency(config)
    usd_str = f"${usd:.4f} USD"
    if code == "USD" or rate == 1.0:
        return usd_str
    local = usd * rate
    return f"${usd:.4f} USD / {symbol}{local:.2f} {code}"

def fmt_tokens(n: int) -> str:
    return f"{n:,}"


# ── Project helpers ────────────────────────────────────────────────────────────

def get_project_hash(cwd: str = None) -> str:
    """Convert /Users/foo/bar_baz → -Users-foo-bar-baz (mirrors Claude Code's hash)"""
    path = os.path.abspath(cwd or os.getcwd())
    return path.replace("/", "-").replace("_", "-")

def find_newest_jsonl(project_hash: str) -> Path | None:
    hash_dir = PROJECTS_DIR / project_hash
    if not hash_dir.exists():
        return None
    files = sorted(hash_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


# ── Report ────────────────────────────────────────────────────────────────────

def build_report(cwd: str = None, show_all: bool = False) -> str:
    cwd = os.path.abspath(cwd or os.getcwd())
    config = load_config()
    config = fetch_exchange_rates(config)

    lines = []
    bar = "━" * 44
    lines.append(f"[getcost] {cwd}")
    lines.append(bar)

    # Current session
    project_hash = get_project_hash(cwd)
    jsonl = find_newest_jsonl(project_hash)
    if jsonl:
        sess = parse_session(jsonl)
        t = sess["tokens"]
        lines.append("本 session（進行中）")
        lines.append(f"  input         {fmt_tokens(t['input'])} tokens")
        lines.append(f"  cache_write   {fmt_tokens(t['cache_write'])} tokens")
        lines.append(f"  cache_read    {fmt_tokens(t['cache_read'])} tokens")
        lines.append(f"  output        {fmt_tokens(t['output'])} tokens")
        lines.append(f"  費用：{format_cost(sess['cost_usd'], config)}")
    else:
        lines.append("本 session：（找不到 JSONL 資料）")

    lines.append("")

    # History from sessions.json
    sessions_file = Path(cwd) / ".getcost" / "sessions.json"
    if sessions_file.exists():
        try:
            data = json.loads(sessions_file.read_text())
            total = data.get("project_total", {})
            session_list = data.get("sessions", [])
            count = len(session_list)
            total_tok = sum(total.get(k, 0) for k in ("input_tokens", "cache_write_tokens", "cache_read_tokens", "output_tokens"))
            lines.append(f"目錄歷史總計（{count} sessions）")
            lines.append(f"  總 tokens：{fmt_tokens(total_tok)}")
            lines.append(f"  總費用：{format_cost(total.get('cost_usd', 0.0), config)}")

            if show_all and session_list:
                lines.append("")
                lines.append("  ── Session 明細 ──")
                for s in session_list:
                    t2 = s.get("tokens", {})
                    tok2 = sum(t2.get(k, 0) for k in ("input", "cache_write", "cache_read", "output"))
                    lines.append(f"  {s.get('date','?')[:10]}  {fmt_tokens(tok2):>10} tokens  {format_cost(s.get('cost_usd', 0.0), config)}")
        except (json.JSONDecodeError, OSError):
            lines.append("目錄歷史：（讀取 sessions.json 失敗）")
    else:
        lines.append("目錄歷史：（尚無記錄 — session 結束後自動建立）")

    lines.append(bar)

    # Exchange rate footer
    code, symbol, rate = detect_currency(config)
    if code != "USD":
        updated = config.get("exchange_rates_updated", "")
        date_str = updated[:10] if updated else "unknown"
        lines.append(f"匯率：1 USD = {rate:.2f} {code}（cache：{date_str}）")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--session", metavar="FILE", help="Parse single JSONL session file")
    g.add_argument("--report",  action="store_true", help="Full report for current directory")
    p.add_argument("--all",  action="store_true", help="Show per-session breakdown (with --report)")
    p.add_argument("--cwd",  metavar="DIR", help="Override working directory")
    args = p.parse_args()

    if args.session:
        config = load_config()
        config = fetch_exchange_rates(config)
        sess = parse_session(args.session)
        t = sess["tokens"]
        total_tok = sum(t.values())
        print(f"Session : {sess['session_id']}")
        print(f"Tokens  : input={fmt_tokens(t['input'])}  cache_write={fmt_tokens(t['cache_write'])}  cache_read={fmt_tokens(t['cache_read'])}  output={fmt_tokens(t['output'])}")
        print(f"Total   : {fmt_tokens(total_tok)} tokens")
        print(f"Cost    : {format_cost(sess['cost_usd'], config)}")
    else:
        print(build_report(cwd=args.cwd, show_all=args.all))

if __name__ == "__main__":
    main()
