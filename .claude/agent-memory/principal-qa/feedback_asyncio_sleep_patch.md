---
name: asyncio.sleep patch pattern for instant polling tests
description: How to patch asyncio.sleep so polling tests run in milliseconds
type: feedback
---

Patch `xai_cli.api.asyncio.sleep` (not `asyncio.sleep`) using `AsyncMock`:

```python
from unittest.mock import AsyncMock, patch

with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
    ...
```

**Why:** `poll_video` and `_get_with_server_retry` both call `asyncio.sleep`. Without patching, the backoff delays (2^0=1s, 2^1=2s, poll delay 5s) make the test suite take minutes. The patch target must be the module-level reference, not the global.

**How to apply:** Every async test that exercises poll_video, _get_with_server_retry, or server retry logic must include this patch. For rate-limit Retry-After tests, use `side_effect=fake_sleep` instead of `AsyncMock` so you can assert the sleep value passed.
