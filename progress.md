# getcost — Implementation Progress

## Step 1 — Project spec & README
- [x] CLAUDE.md — full implementation spec
- [x] README.md — user-facing documentation
- [x] git init + initial commit
> DONE

---

## Step 2 — Core calculation library (`bin/getcost-calc.py`)
- [ ] Parse JSONL: extract all `usage` objects from a session file
- [ ] Sum tokens: input, cache_write, cache_read, output per session
- [ ] Pricing table: built-in prices for opus-4-7, sonnet-4-6, haiku-4-5, fallback
- [ ] Cost calculation: per-model USD cost from token counts
- [ ] Locale detection: LC_MONETARY → LANG → default USD
- [ ] Currency conversion: fetch/cache exchange rates from open.er-api.com
- [ ] Format output: `$0.42 USD / NT$13.44 TWD` style
- [ ] CLI mode: `python3 getcost-calc.py --session <file>` for manual testing

---

## Step 3 — Stop hook (`bin/getcost-session-end.py`)
- [ ] Find current project-hash from CWD
- [ ] Find newest JSONL file in `~/.claude/projects/{hash}/`
- [ ] Call getcost-calc to sum session tokens + cost
- [ ] Load/create `{project}/.getcost/sessions.json`
- [ ] Append session record with id, date, model, tokens, cost_usd
- [ ] Update `project_total` cumulative fields
- [ ] Reset / clear `checkpoint.json` current session accumulated
- [ ] Print session-end summary to terminal

---

## Step 4 — PostToolUse checkpoint hook (`bin/getcost-checkpoint.py`)
- [ ] Read `{project}/.getcost/checkpoint.json` → `last_reported_at`
- [ ] Compute elapsed minutes since last report
- [ ] If elapsed < interval → exit silently (exit 0)
- [ ] If elapsed ≥ interval → read current session JSONL, calc tokens + cost
- [ ] Print checkpoint one-liner to terminal
- [ ] Write new `last_reported_at` timestamp to checkpoint.json

---

## Step 5 — Hook registration manager (`bin/getcost-settings-hook.py`)
- [ ] `add-stop` subcommand: inject Stop hook into `~/.claude/settings.json`
- [ ] `add-posttooluse` subcommand: inject PostToolUse hook into settings.json
- [ ] `remove` subcommand: remove both hooks (identified by marker string)
- [ ] Dedup guard: skip if hook already present
- [ ] Atomic write: tempfile + os.replace to avoid corruption

---

## Step 6 — `/getcost` skill (`skill.md`)
- [ ] Skill frontmatter: name, description, allowed-tools
- [ ] Run `getcost-calc.py --report` to gather data
- [ ] Format and display: current session breakdown + directory total
- [ ] Show exchange rate cache date
- [ ] Handle `all` argument: per-session detail list
- [ ] Handle missing `.getcost/` gracefully (first run message)

---

## Step 7 — `setup` script
- [ ] Prereq check: git, python3, curl
- [ ] `install`: clone repo → deploy skill.md → register hooks → init `.getcost/` + `.gitignore`
- [ ] `update`: git pull → redeploy skill.md (preserve .getcost/ data)
- [ ] `uninstall`: remove hooks → remove copied skill files (keep .getcost/ data)
- [ ] Init `~/.getcost/config.json` if not exists (with defaults)
- [ ] Fetch initial exchange rates during install
- [ ] Post-install message: restart Claude Code to activate

---

## Step 8 — Integration test
- [ ] Create fixture: sample JSONL with mixed models + usage data
- [ ] Test: token sum matches expected values
- [ ] Test: USD cost calculation matches expected for each model
- [ ] Test: locale detection picks correct currency
- [ ] Test: checkpoint interval gate (suppress / show logic)
- [ ] Test: sessions.json append + project_total accumulation
- [ ] Test: setup install idempotency (run twice, no duplicate hooks)
