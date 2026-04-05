---
name: xAI API live facts
description: Verified endpoint shapes, terminal states, and response structure for the xAI video generation API — deviates from the skill reference in several places
type: project
---

The live API (verified 2026-04-05) differs from the polling-patterns.md skill reference in these ways:

- Submit: `POST https://api.x.ai/v1/videos/generations` (not `/video/generations`)
- Poll: `GET https://api.x.ai/v1/videos/{request_id}` (not `/video/generations/{id}`)
- Model name: `grok-imagine-video`
- Terminal states: `done`, `expired`, `failed` — NOT `succeeded` (the skill uses `succeeded`)
- Success response: `data["video"]["url"]` nested, not `data["video_url"]`
- `generate_video` returns `data["id"]` as the request_id
- Recommended initial poll delay: 5s (skill reference says 2s — task spec overrides this)

**Why:** The skill was written against an earlier draft; the live docs take precedence.

**How to apply:** Always use the live facts above when writing or reviewing API client code. Do not trust the skill reference for endpoint paths, terminal state names, or response field names.
