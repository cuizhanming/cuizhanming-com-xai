---
name: xAI API shape and terminal states
description: Authoritative endpoint URLs, field names, and terminal states for the xAI video generation API
type: project
---

These override the skill reference at `.claude/skills/xai-test-strategy/references/polling-fixtures.md`.

- Submit endpoint: `POST https://api.x.ai/v1/videos/generations` (plural, no `/generation`)
- Poll endpoint: `GET https://api.x.ai/v1/videos/{id}`
- Terminal states: `done`, `expired`, `failed` (NOT `succeeded`)
- In-progress state: `pending`
- Success response shape: `{"id": "...", "status": "done", "url": "https://..."}`
  - `url` is at top level, NOT nested under `video`
- Failed response shape: `{"id": "...", "status": "failed", "error": {...}}`
- JSON CLI output field: `"url"` (not `"video_url"`)

**Why:** The skill reference was written for an older API revision and uses wrong field names and a different URL path.

**How to apply:** Always use these shapes when constructing respx mocks and when asserting on result JSON.
