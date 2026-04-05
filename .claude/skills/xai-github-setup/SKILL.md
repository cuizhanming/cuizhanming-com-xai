---
name: xai-github-setup
description: GitHub repo creation and initial push runbook for the xAI CLI project. Background knowledge for the principal-sre agent. Auto-loads whenever working on repo setup, git init, pushing to GitHub, creating remotes, or configuring the first push for this project. Use this whenever the user mentions creating a repo, setting up git, pushing code to GitHub, or configuring CI on a fresh clone.
---

# GitHub Repo Setup — xAI CLI

## Prerequisites

- `gh` CLI authenticated with `repo` scope:
  ```bash
  gh auth status
  # Expected: ✓ Logged in to github.com as <user> with scopes: repo, ...
  ```
- Working directory: `/Users/aibassador/Workspace/github/cuizhanming-com-xai` (or any project root using this pattern)

---

## Runbook

### 1. Init git (if not already a repo)

```bash
git init
git checkout -b main
```

Always start on `main` to avoid the legacy `master` default.

### 2. Create `.gitignore` before staging

Create (or verify) a `.gitignore` that excludes at minimum:

```gitignore
.venv/
.env
.env.*
*.mp4
*.mov
.claude/settings.local.json
__pycache__/
*.egg-info/
dist/
```

**Why first:** `git add .` without this stages `.venv/` (hundreds of files), secrets, and generated video artifacts. Retroactively untracking files from git history is painful — do this before any staging.

### 3. Create the GitHub repo

```bash
gh repo create <repo-name> \
  --public \
  --description "<one-line description>" \
  --source=. \
  --remote=origin
```

`--source=.` creates the repo, links the current directory, and registers `origin` as the remote in one step — no separate `git remote add origin <url>` needed.

**Naming convention for this project:** `cuizhanming-com-<project>` (e.g. `cuizhanming-com-xai`)

### 4. Stage, verify, commit, push

```bash
git add .
git status          # verify: no .venv/, no .env files, no *.mp4
git commit -m "feat: <initial commit message>"
git push -u origin main
```

`-u` sets the upstream so future `git push` / `git pull` need no arguments.

---

## Conventions

| Setting | Value |
|---|---|
| Default visibility | public |
| Default branch | `main` |
| Remote name | `origin` |
| Repo naming | `cuizhanming-com-<project>` |

---

## Common mistakes

- **Skipping `.gitignore`** before `git add .` — stages `.venv/` and secrets
- **Running `git remote add origin`** separately — `gh repo create --source=.` does this automatically
- **Using `master`** as the default branch — always `git checkout -b main` first

---

## Reference

Full annotated runbook with exact commands from the initial setup:
See [`../xai-release-workflow/github-setup.md`](../xai-release-workflow/github-setup.md)
