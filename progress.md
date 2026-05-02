# getcost — Implementation Progress

## Step 1 — Project spec, README & GitHub remote
- [x] CLAUDE.md — full implementation spec
- [x] README.md — user-facing documentation
- [x] git init + initial commit
- [x] Create GitHub repo: github.com/ibalasite/getcost
- [x] Set remote origin + push
> DONE

---

## Step 2 — Repository structure
- [x] Create `skills/` directory
- [x] Create `skills/getcost-upgrade/` placeholder (skill written in Step 8)
- [ ] Update CLAUDE.md to reflect final repo layout

---

## Step 3 — Core calculation library (`bin/getcost-calc.py`)
- [x] Parse JSONL: iterate lines, extract entries that contain a `usage` object
- [x] Sum tokens per session: input, cache_creation_input, cache_read_input, output
- [x] Handle multi-model sessions: each JSONL line has its own `model` field, apply per-line pricing
- [x] Built-in pricing table: opus-4-7, sonnet-4-6, haiku-4-5, unknown fallback
- [x] USD cost calculation from token counts
- [x] Locale detection: check `LC_MONETARY` → `LANG` → default USD
- [x] Exchange rate: load from `~/.getcost/config.json`; if absent or stale (>24h), fetch from `open.er-api.com` and save
- [x] Format output string: `$0.42 USD / NT$13.44 TWD`
- [x] CLI entry point: `python3 getcost-calc.py --session <file>` prints result (for user verification)
> DONE

---

## Step 4 — Stop hook (`bin/getcost-session-end.py`)
- [x] Derive project-hash from `$PWD`: replace `/` with `-`
- [x] Find newest `.jsonl` file under `~/.claude/projects/{hash}/`
- [x] Call `getcost-calc` logic to get session token totals + cost
- [x] Lazily create `{PWD}/.getcost/` and `{PWD}/.getcost/.gitignore` (content: `*`) on first run
- [x] Load `{PWD}/.getcost/sessions.json` (create if missing)
- [x] Append session record: id, date, model summary, tokens, cost_usd
- [x] Recompute and update `project_total` cumulative fields
- [x] Write `{PWD}/.getcost/checkpoint.json` with `last_reported_at` reset to epoch
- [x] Print session-end summary to stdout
> DONE

---

## Step 5 — PostToolUse checkpoint hook (`bin/getcost-checkpoint.py`)
- [x] Derive project-hash from `$PWD`
- [x] Find newest `.jsonl` in `~/.claude/projects/{hash}/`
- [x] Lazily create `{PWD}/.getcost/` and `{PWD}/.getcost/.gitignore` (content: `*`) on first run
- [x] Read `{PWD}/.getcost/checkpoint.json` → `last_reported_at` (treat missing as epoch)
- [x] Compute elapsed minutes
- [x] If elapsed < interval → exit 0 silently
- [x] If elapsed ≥ interval: calc current session token totals + cost, print one-liner, update `last_reported_at`
- [x] Read interval from `~/.getcost/config.json` `checkpoint_interval_minutes` (default: 5)
> DONE

---

## Step 6 — Hook registration manager (`bin/getcost-settings-hook.py`)
- [x] `add-stop` subcommand: inject Stop hook entry into `~/.claude/settings.json`
- [x] `add-posttooluse` subcommand: inject PostToolUse hook entry into settings.json
- [x] `remove` subcommand: remove both hooks by marker string
- [x] Dedup guard: skip silently if identical hook already present
- [x] Atomic write: tempfile + `os.replace` to avoid settings.json corruption
- [x] Create `~/.claude/settings.json` with empty skeleton if file does not exist
> DONE

---

## Step 7 — `/getcost` skill (`skill.md`)
- [x] Skill frontmatter: name, description, trigger patterns, allowed-tools
- [x] Invoke `bin/getcost-calc.py --report` via Bash tool to gather current session + totals
- [x] Display formatted report: current session token breakdown + directory total
- [x] Show exchange rate with cache date
- [x] Handle `all` argument: show per-session detail list from sessions.json
- [x] Handle missing `.getcost/` gracefully: print first-run hint
> DONE

---

## Step 8 — `/getcost-upgrade` skill (`skills/getcost-upgrade/skill.md`)
- [x] Skill frontmatter: name, description, allowed-tools
- [x] `git pull` in `~/.claude/skills/getcost/`
- [x] Redeploy sub-skills: copy `~/.claude/skills/getcost/skills/*` → `~/.claude/skills/`
- [x] Print upgrade summary: old version → new version (git log --oneline -1)
> DONE

---

## Step 9 — `setup` script
- [x] Prereq check: git, python3, curl; exit with clear message if missing
- [x] `install` action:
  - Clone repo to `~/.claude/skills/getcost/`
  - Deploy sub-skills: copy `~/.claude/skills/getcost/skills/*` → `~/.claude/skills/`
  - Run `bin/getcost-settings-hook.py add-stop`
  - Run `bin/getcost-settings-hook.py add-posttooluse`
  - Init `~/.getcost/config.json` with defaults if not present
  - Fetch exchange rates on first install
  - Print: "Restart Claude Code to activate hooks"
- [x] `update` action:
  - `git pull` in `~/.claude/skills/getcost/`
  - Redeploy sub-skills: copy `~/.claude/skills/getcost/skills/*` → `~/.claude/skills/`
  - Print update summary
- [x] `uninstall` action:
  - Remove hooks via `bin/getcost-settings-hook.py remove`
  - Remove deployed sub-skills from `~/.claude/skills/` (only those sourced from `skills/*`)
  - Remove `~/.claude/skills/getcost/`
  - Leave `~/.getcost/` and all `.getcost/` project data intact
> DONE

---

## Step 10 — Verify commands (user runs after install)

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
