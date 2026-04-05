---
name: generate_video has no server retry; only GET paths retry
description: POST /videos/generations does not use _get_with_server_retry — a single 500 raises immediately
type: project
---

`generate_video` calls `self._client.post(...)` directly. A 500 from the submit endpoint raises `XAIServerError` immediately with no retry.

Only `get_video_status` and `poll_video` use `_get_with_server_retry`, which retries up to 3 times with exponential backoff (2^attempt seconds between retries).

**Why:** This is the actual implementation in api.py. It's a potential gap worth raising with the AI engineer — submit errors aren't retried but poll errors are.

**How to apply:** When writing tests for generate_video 500 behavior, assert `respx.calls.call_count == 1` (not 3). When writing tests for poll or status 500, assert call_count == 3 and sleep call_count == 2.
