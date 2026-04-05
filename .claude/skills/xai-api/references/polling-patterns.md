# Polling Implementation Patterns

## Canonical Async Polling (httpx)

```python
import asyncio
import httpx
from typing import AsyncIterator

async def poll_video_generation(
    client: httpx.AsyncClient,
    generation_id: str,
    *,
    timeout_seconds: float = 600,
    on_status: Callable[[str], None] | None = None,
) -> dict:
    """Poll until terminal state. Raises on failure or timeout."""
    delay = 2.0
    elapsed = 0.0

    while elapsed < timeout_seconds:
        resp = await client.get(f"/video/generations/{generation_id}")
        resp.raise_for_status()
        data = resp.json()
        status = data["status"]

        if on_status:
            on_status(status)

        if status == "succeeded":
            return data
        if status == "failed":
            error = data.get("error", {})
            raise VideoGenerationError(
                code=error.get("code", "unknown"),
                message=error.get("message", "Video generation failed"),
            )

        await asyncio.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 30.0)  # cap at 30s

    raise VideoGenerationTimeoutError(
        generation_id=generation_id,
        timeout_seconds=timeout_seconds,
    )
```

## Progress Callback Pattern

The `on_status` callback is how polling surfaces state to the CLI layer. The CLI engineer wires this to a spinner or status line. The API client must NOT do any printing — keep concerns separated.

```python
# CLI layer wires the callback:
def _on_status(status: str) -> None:
    spinner.text = f"Status: {status}"

result = await poll_video_generation(client, gen_id, on_status=_on_status)
```

## Rate Limit Handling

When receiving a 429, read the `Retry-After` header before sleeping:

```python
if resp.status_code == 429:
    retry_after = float(resp.headers.get("Retry-After", delay))
    await asyncio.sleep(retry_after)
    continue
```

## Sync Alternative (requests)

Only use if the project has already committed to `requests`. The pattern is identical but uses `time.sleep` and `requests.Session`.
