---
name: xai-release-workflow
description: Step-by-step release checklist for the xAI CLI — version bump, changelog, build, PyPI publish, GitHub tag and release. Invoke manually with /xai-release-workflow before cutting any release.
disable-model-invocation: true
argument-hint: "[version e.g. 1.0.0]"
---

# xAI CLI Release Workflow

Releasing version: $ARGUMENTS

Work through these steps in order. Do not skip steps.

## Pre-flight Checks

1. Confirm you are on the `main` branch with no uncommitted changes:
   ```bash
   git status
   git log --oneline -5
   ```
2. Confirm CI is green on the latest commit (check GitHub Actions via the github MCP tool or `gh run list`)
3. Confirm QA sign-off: `uv run pytest` must pass with zero failures

## Step 1 — Bump Version

Update `version` in `pyproject.toml`:
```toml
[project]
version = "$ARGUMENTS"
```

## Step 2 — Update Changelog

Add a `## [$ARGUMENTS] - $(date +%Y-%m-%d)` section to `CHANGELOG.md` listing:
- New features
- Bug fixes
- Breaking changes (if any)

## Step 3 — Final Build Check

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
```

All commands must exit 0. Fix any failures before proceeding.

## Step 4 — Commit and Tag

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release v$ARGUMENTS"
git tag -a "v$ARGUMENTS" -m "Release v$ARGUMENTS"
```

## Step 5 — Push and Publish

```bash
git push origin main
git push origin "v$ARGUMENTS"
```

The `v$ARGUMENTS` tag triggers the CD workflow (`.github/workflows/release.yml`) which runs `uv build` and `uv publish` automatically.

Verify the publish via the github MCP tool: check that the release workflow completed successfully and the package appears on PyPI.

## Step 6 — Create GitHub Release

Use the github MCP tool to create a GitHub release for tag `v$ARGUMENTS` with the changelog content as the release notes.

## Rollback

If the PyPI publish succeeds but the release is broken:
- PyPI does not allow deleting versions — yank it instead: `uv publish --yank v$ARGUMENTS`
- Fix forward in a patch release `$ARGUMENTS.patch+1`
