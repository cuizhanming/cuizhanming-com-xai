# GitHub Repo Setup Runbook

## Prerequisites
- `gh` CLI authenticated (`gh auth status`)
- Working directory is the project root

## Steps

### 1. Verify gh auth
```bash
gh auth status
```
Confirms the active account and that the token has `repo` scope. Expected output shows `✓ Logged in to github.com`.

### 2. Init git (if not already)
```bash
git init
git checkout -b main
```
The working directory was not a git repo. `git init` initializes `.git/`, then `git checkout -b main` creates the default branch named `main` (avoids the legacy `master` default).

### 3. Create a .gitignore before staging
Create a project-level `.gitignore` to exclude at minimum:
- `.venv/` — uv virtual environment
- `.env`, `.env.*` — API keys and secrets
- `*.mp4`, `*.mov` — generated video artifacts (large binaries, not source)
- `.claude/settings.local.json` — machine-specific tool permissions, not portable

Without this step, `git add .` will stage the virtual environment (hundreds of files) and any local secrets.

### 4. Create repo on GitHub
```bash
gh repo create cuizhanming-com-xai \
  --public \
  --description "CLI for xAI APIs — video generation" \
  --source=. \
  --remote=origin
```
`--source=.` links the current directory and registers `origin` as the remote automatically. No manual `git remote add` needed. Returns the repo URL on success.

### 5. Stage, commit, push
```bash
git add .
git status                         # verify staged files look correct — no secrets, no .venv
git commit -m "feat: add Phase 1 image-to-video generation feature"
git push -u origin main
```
`-u` sets the upstream so future `git push` / `git pull` need no arguments.

## Notes
- Repo naming convention: `cuizhanming-com-<project>` (e.g. `cuizhanming-com-xai`)
- Default visibility: public
- Default branch: `main`
- Always create `.gitignore` before the first `git add .` — retroactively untracking files from git history is painful
- `gh repo create --source=.` sets up the remote automatically; skip `git remote add origin <url>` when using this flag
- The `gh` token must have `repo` scope; OIDC tokens from GitHub Actions also work for CI-driven repo creation
