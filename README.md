# getcost

Track Claude Code token usage and costs per project directory.

Automatically calculates spending at session end, shows periodic checkpoints during active work, and provides an on-demand cost summary command.

---

## What it does

- **Session end** — when you close Claude Code, prints total tokens used and cost in USD + your local currency
- **Every 5 minutes** — during active work, prints a running cost checkpoint (zero noise when idle)
- **`/getcost`** — call anytime to see current session spend and all-time totals for this directory

---

## Requirements

- Claude Code CLI
- Python 3.8+
- `git`, `curl`
- Internet access at install time (for exchange rate fetch)

---

## Install

```bash
git clone https://github.com/your-org/getcost.git
cd getcost
./setup install
```

Restart Claude Code after install to activate hooks.

To install into a specific project directory, navigate there first:

```bash
cd /path/to/your/project
~/.claude/skills/getcost/setup install
```

---

## Uninstall

```bash
~/.claude/skills/getcost/setup uninstall
```

Your `.getcost/` data files are preserved. Delete them manually if needed.

---

## Update

```bash
~/.claude/skills/getcost/setup update
```

---

## Usage

### In Claude Code

```
/getcost          # summary: current session + directory total
/getcost all      # same, plus per-session breakdown
```

### Example output

```
[getcost] /Users/you/projects/myapp
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
本 session（進行中）
  input        3,201 tokens
  cache_write  12,500 tokens
  cache_read   45,000 tokens
  output          820 tokens
  費用：$0.21 USD / NT$6.72

目錄歷史總計（12 sessions）
  總 tokens：2,891,023
  總費用：$27.41 USD / NT$877.12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
匯率：1 USD = 32.05 TWD（cache：2026-05-03）
```

---

## Currency detection

getcost detects your local currency from system locale (`LC_MONETARY`, `LANG`):

| Locale | Currency |
|--------|----------|
| `zh_TW` | TWD (NT$) |
| `zh_HK` | HKD (HK$) |
| `ja` | JPY (¥) |
| `ko` | KRW (₩) |
| `de`, `fr`, `es`, `it`, `pt` | EUR (€) |
| `en` or unknown | USD ($) |

To override, set `preferred_currency` in `~/.getcost/config.json`:

```json
{ "preferred_currency": "TWD" }
```

---

## Pricing

Built-in pricing table (USD per 1M tokens):

| Model | Input | Output | Cache Write | Cache Read |
|-------|-------|--------|-------------|------------|
| claude-opus-4-7 | $15.00 | $75.00 | $18.75 | $1.50 |
| claude-sonnet-4-6 | $3.00 | $15.00 | $3.75 | $0.30 |
| claude-haiku-4-5 | $0.80 | $4.00 | $1.00 | $0.08 |

Override any model price in `~/.getcost/config.json`:

```json
{
  "pricing_override": {
    "claude-sonnet-4-6": { "input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30 }
  }
}
```

---

## Data files

All data lives in `.getcost/` inside your project directory:

```
your-project/
└── .getcost/
    ├── sessions.json      # per-session records + cumulative totals
    ├── checkpoint.json    # last 5-min checkpoint timestamp
    └── .gitignore         # auto-created, ignores entire .getcost/
```

Global config and exchange rate cache:

```
~/.getcost/
└── config.json            # preferred_currency, checkpoint_interval_minutes, pricing_override, exchange rates
```

---

## Configuration (`~/.getcost/config.json`)

```json
{
  "preferred_currency": "TWD",
  "checkpoint_interval_minutes": 5,
  "pricing_override": {},
  "exchange_rates": {
    "TWD": 32.05,
    "JPY": 155.2,
    "EUR": 0.92,
    "HKD": 7.78,
    "KRW": 1350.0
  },
  "exchange_rates_updated": "2026-05-03T00:00:00Z"
}
```

---

## Known limitations

- **Checkpoint requires tool calls** — the 5-min checkpoint fires via `PostToolUse`. If you're idle (no tool calls), it won't trigger. That's fine: idle = no token consumption.
- **Exchange rate is cached** — updated every 24 hours, not real-time.
- **In-progress session cost is approximate** — final accurate cost is calculated at session end.
