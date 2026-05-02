---
name: getcost-upgrade
description: |
  Upgrade the getcost installation to the latest version from GitHub.
  Use when the user invokes /getcost-upgrade.
allowed-tools:
  - Bash
---

# /getcost-upgrade

Pull the latest getcost and redeploy sub-skills.

---

## Step 1 — Guard: installed?

```bash
test -d "$HOME/.claude/skills/getcost/.git"
```

**[AI 指令]** If not found, output:
```
[getcost] Not installed. Run setup install first.
```
Then stop.

---

## Step 2 — Pull latest

```bash
git -C "$HOME/.claude/skills/getcost" pull --ff-only
```

**[AI 指令]** Run via Bash. If it fails (merge conflict, diverged), output the error and suggest:
```
[getcost-upgrade] Pull failed. Run manually:
  cd ~/.claude/skills/getcost && git fetch && git reset --hard origin/main
```

---

## Step 3 — Redeploy sub-skills

```bash
SKILLS_SRC="$HOME/.claude/skills/getcost/skills"
SKILLS_DST="$HOME/.claude/skills"
for d in "$SKILLS_SRC"/*/; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  rm -rf "$SKILLS_DST/$name"
  cp -r "$d" "$SKILLS_DST/$name"
  echo "  · redeployed $name"
done
```

---

## Step 4 — Show summary

```bash
git -C "$HOME/.claude/skills/getcost" log --oneline -1
```

Display: `[getcost-upgrade] Updated to: {commit line}`
