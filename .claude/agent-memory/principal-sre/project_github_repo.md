---
name: GitHub repo and gitignore setup
description: The cuizhanming-com-xai GitHub repo was created on 2026-04-05; notes on what must be excluded from version control
type: project
---

The GitHub repo `cuizhanming-com-xai` (public) is at https://github.com/cuizhanming/cuizhanming-com-xai, owned by account `cuizhanming`. The `main` branch is the default and upstream is configured.

A `.gitignore` was created in the initial commit. Critical exclusions:
- `.claude/settings.local.json` — machine-specific tool permissions, varies per developer
- `*.mp4`, `*.mov`, `*.avi` — video generation artifacts (can be large, not source code)
- `.venv/` — uv-managed virtual environment
- `.env`, `.env.*` — API keys

**Why:** The first `git add .` without a `.gitignore` would have staged `.venv/` (hundreds of files) and `vg-dl-001.mp4` (a test artifact). Local settings contain `WebFetch` domain allowlists that are personal.

**How to apply:** Always write `.gitignore` before running `git add .` on a new project. When adding new features that produce file output (images, videos), add the extension pattern to `.gitignore` before the first test run.
