# Polling State Machine Test Fixtures

## respx Multi-Response Fixture (httpx)

```python
import pytest, respx, httpx

@pytest.fixture
def mock_successful_poll(respx_mock):
    """Simulates queued → processing → succeeded."""
    responses = [
        httpx.Response(200, json={"id": "vg-1", "status": "queued"}),
        httpx.Response(200, json={"id": "vg-1", "status": "processing"}),
        httpx.Response(200, json={
            "id": "vg-1",
            "status": "succeeded",
            "video_url": "https://example.com/video.mp4"
        }),
    ]
    respx_mock.get("https://api.x.ai/v1/video/generations/vg-1").mock(
        side_effect=responses
    )
    return respx_mock

@pytest.fixture
def mock_failed_poll(respx_mock):
    """Simulates queued → failed with error payload."""
    responses = [
        httpx.Response(200, json={"id": "vg-2", "status": "queued"}),
        httpx.Response(200, json={
            "id": "vg-2",
            "status": "failed",
            "error": {"code": "content_policy_violation", "message": "Prompt rejected"}
        }),
    ]
    respx_mock.get("https://api.x.ai/v1/video/generations/vg-2").mock(
        side_effect=responses
    )
    return respx_mock

@pytest.fixture
def mock_timeout_poll(respx_mock):
    """Always returns processing — triggers timeout."""
    respx_mock.get("https://api.x.ai/v1/video/generations/vg-3").mock(
        return_value=httpx.Response(200, json={"id": "vg-3", "status": "processing"})
    )
    return respx_mock
```

## Timeout Test Pattern

Use a short timeout to avoid slow tests:

```python
import pytest

@pytest.mark.asyncio
async def test_polling_timeout(mock_timeout_poll, xai_client):
    with pytest.raises(VideoGenerationTimeoutError) as exc_info:
        await xai_client.wait_for_generation("vg-3", timeout_seconds=0.1)
    assert exc_info.value.generation_id == "vg-3"
```

## Rate Limit Retry Fixture

```python
@pytest.fixture
def mock_rate_limit_then_success(respx_mock):
    """429 on first poll, then succeeds."""
    responses = [
        httpx.Response(429, headers={"Retry-After": "1"}),
        httpx.Response(200, json={
            "id": "vg-4",
            "status": "succeeded",
            "video_url": "https://example.com/video.mp4"
        }),
    ]
    respx_mock.get("https://api.x.ai/v1/video/generations/vg-4").mock(
        side_effect=responses
    )
    return respx_mock
```
