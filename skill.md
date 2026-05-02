---
name: getcost
description: |
  Show Claude Code token usage and costs for the current project directory.
  Reports current session spend and all-time directory total in USD + local currency.
  Use when the user invokes /getcost or asks about token costs, spending, or usage.
allowed-tools:
  - Bash
---

# /getcost — Token Cost Report

Show token usage and costs for the current project.

---

## Step 1 — Guard: runtime installed?

```bash
test -f "$HOME/.claude/skills/getcost/bin/getcost-calc.py"
```

**[AI 指令]** If not found, output:

```
[getcost] Not installed. Run:
  git clone https://github.com/ibalasite/getcost.git ~/.claude/skills/getcost
  ~/.claude/skills/getcost/setup install
```

Then stop.

---

## Step 2 — Parse argument

Check if user passed `all` as an argument (e.g. `/getcost all`).

```bash
# _ARG is "all" if user wrote "/getcost all", otherwise empty
_ARG=""
```

---

## Step 3 — Run report

```bash
python3 "$HOME/.claude/skills/getcost/bin/getcost-calc.py" \
  --report \
  --cwd "$PWD" \
  ${_ARG:+--all}
```

**[AI 指令]** Run via Bash tool. Display the full output verbatim to the user. Do not summarise or reformat.

---

## Step 4 — Error handling

If the script exits non-zero or output contains `ERROR`:
- Check if `$PWD/.getcost/` exists. If not: first-run hint — tell user the directory will be created automatically when the current session ends.
- Otherwise: display error and suggest running `/getcost-upgrade`.
