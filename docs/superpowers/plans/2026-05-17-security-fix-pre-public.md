# Security Fix — Pre-Public Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all secrets and PII from the `coach-ai` repository so it can be safely made public on GitHub.

**Architecture:** Four independent fixes applied in order: (1) remove token from current file, (2) remove `.env` from git tracking, (3) remove PII from system prompt, (4) rewrite git history to erase the token from all past commits. History rewrite must be last because it changes commit SHAs and requires a force-push.

**Tech Stack:** Git, git-filter-repo (Python tool), bash

---

## Context for the Executor

A security audit found the following issues in this repository before it is made public:

| # | Severity | File | Issue |
|---|----------|------|-------|
| 1 | CRITICAL | `docs/TELEGRAM_BOT_SETUP.md:7` | Real Telegram bot token hardcoded: `REDACTED_TOKEN` |
| 2 | CRITICAL | git history | Same token present in 70+ commits across `main`, `fix-2`, `feat/dynamic-programs`, `pr-11` |
| 3 | HIGH | `.env` | File is git-tracked (should be ignored) |
| 4 | MEDIUM | `prompts/SYSTEM_PROMPT.md:40` | Real user first name `Fabiano` hardcoded |

**IMPORTANT:** The Telegram bot token `REDACTED_TOKEN` must be **revoked via BotFather before or immediately after** this plan is executed. Editing files does not invalidate a live token — only BotFather revocation does. This step is manual and cannot be scripted.

---

## Task 1: Remove Token from Current File

**Files:**
- Modify: `docs/TELEGRAM_BOT_SETUP.md:7`

- [ ] **Step 1: Verify the token is present on line 7**

```bash
grep -n "8792230414" docs/TELEGRAM_BOT_SETUP.md
```

Expected output:
```
7:✅ **Telegram Bot Token** — You've already provided: `REDACTED_TOKEN`
```

- [ ] **Step 2: Replace line 7 with a safe placeholder**

Replace the current line 7:
```markdown
✅ **Telegram Bot Token** — You've already provided: `REDACTED_TOKEN`
```

With:
```markdown
✅ **Telegram Bot Token** — Set in your `.env` file as `TELEGRAM_BOT_TOKEN=<your_token_from_botfather>`
```

- [ ] **Step 3: Verify token is gone from current file**

```bash
grep -n "8792230414" docs/TELEGRAM_BOT_SETUP.md
```

Expected: no output (empty).

- [ ] **Step 4: Commit**

```bash
git add docs/TELEGRAM_BOT_SETUP.md
git commit -m "fix: remove hardcoded Telegram bot token from setup docs"
```

---

## Task 2: Remove `.env` from Git Tracking

**Files:**
- Untrack: `.env`

- [ ] **Step 1: Confirm `.env` is currently tracked**

```bash
git ls-files .env
```

Expected output: `.env`

- [ ] **Step 2: Verify `.gitignore` already lists `.env`**

```bash
grep "^\.env$" .gitignore
```

Expected output: `.env`

If the output is empty, add `.env` to `.gitignore` before continuing:
```bash
echo ".env" >> .gitignore
```

- [ ] **Step 3: Remove from git index without deleting the local file**

```bash
git rm --cached .env
```

Expected output: `rm '.env'`

- [ ] **Step 4: Verify `.env` is no longer tracked**

```bash
git ls-files .env
```

Expected: no output (empty).

```bash
git status .env
```

Expected: `.env` appears under "Untracked files" or not at all — NOT under "Changes to be committed".

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: stop tracking .env — use .env.example as template"
```

---

## Task 3: Remove Real Name from System Prompt

**Files:**
- Modify: `prompts/SYSTEM_PROMPT.md:40`

- [ ] **Step 1: Verify the name is on line 40**

```bash
grep -n "Fabiano" prompts/SYSTEM_PROMPT.md
```

Expected output:
```
40:* **Name:** Fabiano
```

- [ ] **Step 2: Replace with a generic placeholder**

Change line 40 from:
```markdown
* **Name:** Fabiano
```

To:
```markdown
* **Name:** User
```

- [ ] **Step 3: Verify the change**

```bash
grep -n "Fabiano" prompts/SYSTEM_PROMPT.md
```

Expected: no output.

- [ ] **Step 4: Run existing tests to confirm nothing broke**

```bash
pytest tests/ -v
```

Expected: all tests pass (this change doesn't affect logic).

- [ ] **Step 5: Commit**

```bash
git add prompts/SYSTEM_PROMPT.md
git commit -m "fix: remove personal name from system prompt"
```

---

## Task 4: Rewrite Git History to Erase the Token

> **WARNING:** This rewrites commit SHAs. Any open PRs or forks will diverge. Coordinate with collaborators before running. After this task, a force-push to all remote branches is required.

**Prerequisite:** `git-filter-repo` must be installed.

```bash
pip install git-filter-repo
```

- [ ] **Step 1: Create a backup tag before rewriting**

```bash
git tag backup-pre-filter HEAD
```

- [ ] **Step 2: Create the token replacement file**

Create a temporary file `/tmp/token-replacements.txt` with this exact content (one line):

```
REDACTED_TOKEN==>REDACTED_TOKEN
```

- [ ] **Step 3: Run git-filter-repo to replace token across all history**

```bash
git filter-repo --replace-text /tmp/token-replacements.txt --force
```

Expected output: lines like `Ref 'refs/heads/main' was rewritten` for each branch.

- [ ] **Step 4: Verify the token is gone from all history**

```bash
git log --all -p | grep "8792230414"
```

Expected: no output (empty). If any line is returned, the filter did not work — do not proceed.

- [ ] **Step 5: Verify recent commits still look correct**

```bash
git log --oneline -10
git show HEAD:docs/TELEGRAM_BOT_SETUP.md | head -20
```

Confirm the file content is correct and history is intact (just with token replaced).

- [ ] **Step 6: Re-add the remote and force-push all branches**

```bash
# List current remotes
git remote -v

# Force-push each branch that existed before the rewrite
# Replace 'origin' with your actual remote name if different
git push origin --force --all
git push origin --force --tags
```

> After force-push, any collaborator must run `git fetch --all` and reset their local branches.

- [ ] **Step 7: Clean up temp files**

```bash
rm /tmp/token-replacements.txt
```

---

## Task 5: Final Verification

- [ ] **Step 1: Confirm no secrets remain in working tree**

```bash
grep -rn "8792230414" . --exclude-dir=.git
grep -rn "Fabiano" prompts/ --exclude-dir=.git
git ls-files .env
```

Expected: all three commands return no output.

- [ ] **Step 2: Confirm no secrets remain in git history**

```bash
git log --all -p | grep -E "8792230414|AAHFfXdJRpB"
```

Expected: no output.

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Delete backup tag**

```bash
git tag -d backup-pre-filter
git push origin --delete backup-pre-filter 2>/dev/null || true
```

---

## Manual Step (Cannot Be Scripted)

**Revoke the Telegram bot token via BotFather:**

1. Open Telegram
2. Search for `@BotFather`
3. Send `/mybots`
4. Select your bot
5. Choose **"API Token"**
6. Click **"Revoke current token"**
7. Copy the new token and update your local `.env` file

This is the most critical step. A leaked token that is not revoked remains exploitable even after all git history is cleaned.
