# getcost — Implementation Progress

## Step 1 — Project spec, README & GitHub remote
- [x] CLAUDE.md — full implementation spec
- [x] README.md — user-facing documentation
- [x] git init + initial commit
- [x] Create GitHub repo: github.com/ibalasite/getcost
- [x] Set remote origin + push
> DONE

---

## Step 2 — Core calculation library (`bin/getcost-calc.py`)
- [ ] Parse JSONL: iterate lines, extract entries that contain a `usage` object
- [ ] Sum tokens per session: input, cache_creation_input, cache_read_input, output
- [ ] Handle multi-model sessions: each JSONL line has its own `model` field, apply per-line pricing
- [ ] Built-in pricing table: opus-4-7, sonnet-4-6, haiku-4-5, unknown fallback
- [ ] USD cost calculation from token counts
- [ ] Locale detection: check `LC_MONETARY` → `LANG` → default USD
- [ ] Exchange rate: load from `~/.getcost/config.json`; if absent or stale (>24h), fetch from `open.er-api.com` and save
- [ ] Format output string: `$0.42 USD / NT$13.44 TWD`
- [ ] CLI entry point: `python3 getcost-calc.py --session <file>` prints result (for user verification)

---

## Step 3 — Stop hook (`bin/getcost-session-end.py`)
- [ ] Derive project-hash from `$PWD`: replace `/` with `-`
- [ ] Find newest `.jsonl` file under `~/.claude/projects/{hash}/`
- [ ] Call `getcost-calc` logic to get session token totals + cost
- [ ] Lazily create `{PWD}/.getcost/` and `{PWD}/.getcost/.gitignore` (content: `*`) on first run
- [ ] Load `{PWD}/.getcost/sessions.json` (create if missing)
- [ ] Append session record: id, date, model summary, tokens, cost_usd
- [ ] Recompute and update `project_total` cumulative fields
- [ ] Write `{PWD}/.getcost/checkpoint.json` with `last_reported_at` reset to epoch (so next session starts fresh)
- [ ] Print session-end summary to stdout

---

## Step 4 — PostToolUse checkpoint hook (`bin/getcost-checkpoint.py`)
- [ ] Derive project-hash from `$PWD`
- [ ] Find newest `.jsonl` in `~/.claude/projects/{hash}/`
- [ ] Lazily create `{PWD}/.getcost/` and `{PWD}/.getcost/.gitignore` (content: `*`) on first run
- [ ] Read `{PWD}/.getcost/checkpoint.json` → `last_reported_at` (treat missing as epoch)
- [ ] Compute elapsed minutes
- [ ] If elapsed < interval → exit 0 silently
- [ ] If elapsed ≥ interval: calc current session token totals + cost, print one-liner, update `last_reported_at`
- [ ] Read interval from `~/.getcost/config.json` `checkpoint_interval_minutes` (default: 5)

---

## Step 5 — Hook registration manager (`bin/getcost-settings-hook.py`)
- [ ] `add-stop` subcommand: inject Stop hook entry into `~/.claude/settings.json`
- [ ] `add-posttooluse` subcommand: inject PostToolUse hook entry into settings.json
- [ ] `remove` subcommand: remove both hooks by marker string
- [ ] Dedup guard: skip silently if identical hook already present
- [ ] Atomic write: tempfile + `os.replace` to avoid settings.json corruption
- [ ] Create `~/.claude/settings.json` with empty skeleton if file does not exist

---

## Step 6 — `/getcost` skill (`skill.md`)
- [ ] Skill frontmatter: name, description, trigger patterns, allowed-tools
- [ ] Invoke `bin/getcost-calc.py --report` via Bash tool to gather current session + totals
- [ ] Display formatted report: current session token breakdown + directory total
- [ ] Show exchange rate with cache date
- [ ] Handle `all` argument: show per-session detail list from sessions.json
- [ ] Handle missing `.getcost/` gracefully: print first-run hint

---

## Step 7 — `setup` script
- [ ] Prereq check: git, python3, curl; exit with clear message if missing
- [ ] `install` action:
  - Clone repo to `~/.claude/skills/getcost/` (or pull if already exists)
  - Run `bin/getcost-settings-hook.py add-stop`
  - Run `bin/getcost-settings-hook.py add-posttooluse`
  - Init `~/.getcost/config.json` with defaults if not present
  - Fetch exchange rates on first install
  - Print: "Restart Claude Code to activate hooks"
- [ ] `update` action: git pull in `~/.claude/skills/getcost/` → redeploy `skill.md`
- [ ] `uninstall` action: remove hooks via settings-hook.py → remove `~/.claude/skills/getcost.md`; leave `.getcost/` data intact

---

## Step 8 — Verify commands (user runs after install)

This repo does not run setup or modify the local environment.
After installing, the user verifies with:

```bash
# 1. Check hooks registered correctly
python3 -c "import json; d=json.load(open('$HOME/.claude/settings.json')); print(json.dumps(d.get('hooks',{}), indent=2))"

# 2. Test calc library against a real session file
python3 ~/.claude/skills/getcost/bin/getcost-calc.py --session \
  ~/.claude/projects/$(echo $PWD | sed 's|/|-|g' | sed 's/^-//')/*.jsonl | head -1

# 3. Trigger a manual session-end calculation
python3 ~/.claude/skills/getcost/bin/getcost-session-end.py

# 4. Inspect written sessions.json
cat .getcost/sessions.json | python3 -m json.tool

# 5. Force a checkpoint (set last_reported_at to epoch)
echo '{"last_reported_at":"1970-01-01T00:00:00Z"}' > .getcost/checkpoint.json
python3 ~/.claude/skills/getcost/bin/getcost-checkpoint.py
```
> ← user runs these; not executed in this repo
