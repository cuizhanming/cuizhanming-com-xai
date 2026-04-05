"""
Unit tests for XAIClient — all HTTP interactions mocked via respx.

Key facts about the real implementation:
- generate_video uses self._client.post directly (no server retry)
- get_video_status / poll_video use _get_with_server_retry (3 attempts for 5xx)
- poll_video handles 429 explicitly by sleeping Retry-After seconds
- Terminal states: done, failed, expired
- asyncio.sleep is patched to a no-op so tests run instantly
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from xai_cli.api import XAIClient, _BASE_URL
from xai_cli.exceptions import (
    VideoGenerationError,
    VideoGenerationTimeoutError,
    XAIAuthError,
    XAIRateLimitError,
    XAIServerError,
    XAIValidationError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GENERATE_URL = f"{_BASE_URL}/videos/generations"
VIDEO_ID = "vg-test-001"
POLL_URL = f"{_BASE_URL}/videos/{VIDEO_ID}"
DONE_RESPONSE = {"id": VIDEO_ID, "status": "done", "url": "https://cdn.example.com/v.mp4"}


def _client() -> XAIClient:
    return XAIClient("test-key")


# Patch asyncio.sleep everywhere in the api module so tests run instantly
pytestmark = pytest.mark.asyncio


# ===========================================================================
# generate_video
# ===========================================================================


@respx.mock
async def test_generate_video_happy_path() -> None:
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID})
    )
    async with _client() as client:
        rid = await client.generate_video(prompt="a sunset over mountains")
    assert rid == VIDEO_ID


@respx.mock
async def test_generate_video_401_raises_auth_error() -> None:
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    async with _client() as client:
        with pytest.raises(XAIAuthError):
            await client.generate_video(prompt="test")


@respx.mock
async def test_generate_video_400_raises_validation_error() -> None:
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(400, text="Bad request: invalid prompt")
    )
    async with _client() as client:
        with pytest.raises(XAIValidationError):
            await client.generate_video(prompt="")


@respx.mock
async def test_generate_video_429_raises_rate_limit_error() -> None:
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(429, text="Too Many Requests")
    )
    async with _client() as client:
        with pytest.raises(XAIRateLimitError):
            await client.generate_video(prompt="test")


@respx.mock
async def test_generate_video_500_retries_and_raises_server_error() -> None:
    """generate_video retries up to 3 times on 5xx before raising XAIServerError."""
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        async with _client() as client:
            with pytest.raises(XAIServerError):
                await client.generate_video(prompt="test")
    assert respx.calls.call_count == 3


@respx.mock
async def test_generate_video_with_image_field_in_body() -> None:
    """When image= is provided the request body must contain the image field."""

    def assert_body_has_image(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "image" in body
        assert body["image"] == "data:image/png;base64,abc"
        return httpx.Response(200, json={"id": VIDEO_ID})

    respx.post(GENERATE_URL).mock(side_effect=assert_body_has_image)
    async with _client() as client:
        rid = await client.generate_video(
            prompt="test", image="data:image/png;base64,abc"
        )
    assert rid == VIDEO_ID


@respx.mock
async def test_generate_video_with_reference_images_in_body() -> None:
    """When reference_images= is provided the field must appear in the body."""

    def assert_body(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "reference_images" in body
        assert body["reference_images"] == ["data:image/jpeg;base64,xyz"]
        return httpx.Response(200, json={"id": VIDEO_ID})

    respx.post(GENERATE_URL).mock(side_effect=assert_body)
    async with _client() as client:
        await client.generate_video(
            prompt="test", reference_images=["data:image/jpeg;base64,xyz"]
        )


@respx.mock
async def test_generate_video_without_image_omits_image_field() -> None:
    """Optional fields must not appear in the body when not provided."""

    def assert_no_image(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "image" not in body
        assert "reference_images" not in body
        return httpx.Response(200, json={"id": VIDEO_ID})

    respx.post(GENERATE_URL).mock(side_effect=assert_no_image)
    async with _client() as client:
        await client.generate_video(prompt="a mountain")


# ===========================================================================
# poll_video
# ===========================================================================


@respx.mock
async def test_poll_video_pending_then_done() -> None:
    """pending → done: should return the done payload."""
    respx.get(POLL_URL).mock(
        side_effect=[
            httpx.Response(200, json={"id": VIDEO_ID, "status": "pending"}),
            httpx.Response(200, json=DONE_RESPONSE),
        ]
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        async with _client() as client:
            result = await client.poll_video(VIDEO_ID)
    assert result["status"] == "done"
    assert result["url"] == "https://cdn.example.com/v.mp4"


@respx.mock
async def test_poll_video_pending_then_failed_raises() -> None:
    """pending → failed: must raise VideoGenerationError."""
    respx.get(POLL_URL).mock(
        side_effect=[
            httpx.Response(200, json={"id": VIDEO_ID, "status": "pending"}),
            httpx.Response(
                200,
                json={
                    "id": VIDEO_ID,
                    "status": "failed",
                    "error": {"code": "content_policy", "message": "rejected"},
                },
            ),
        ]
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        async with _client() as client:
            with pytest.raises(VideoGenerationError) as exc_info:
                await client.poll_video(VIDEO_ID)
    assert "failed" in str(exc_info.value)


@respx.mock
async def test_poll_video_pending_then_expired_raises() -> None:
    """pending → expired: must raise VideoGenerationError."""
    respx.get(POLL_URL).mock(
        side_effect=[
            httpx.Response(200, json={"id": VIDEO_ID, "status": "pending"}),
            httpx.Response(200, json={"id": VIDEO_ID, "status": "expired"}),
        ]
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        async with _client() as client:
            with pytest.raises(VideoGenerationError) as exc_info:
                await client.poll_video(VIDEO_ID)
    assert "expired" in str(exc_info.value)


@respx.mock
async def test_poll_video_failed_includes_payload() -> None:
    """VideoGenerationError.payload must carry the raw API response."""
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200,
            json={"id": VIDEO_ID, "status": "failed", "error": {"code": "x"}},
        )
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        async with _client() as client:
            with pytest.raises(VideoGenerationError) as exc_info:
                await client.poll_video(VIDEO_ID)
    assert exc_info.value.payload["status"] == "failed"


@respx.mock
async def test_poll_video_timeout_raises_timeout_error() -> None:
    """When timeout_seconds=0 the loop never runs and timeout is raised immediately."""
    # The route must exist so respx doesn't complain about unmatched calls.
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID, "status": "pending"})
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        async with _client() as client:
            with pytest.raises(VideoGenerationTimeoutError) as exc_info:
                await client.poll_video(VIDEO_ID, timeout_seconds=0)
    assert exc_info.value.request_id == VIDEO_ID


@respx.mock
async def test_poll_video_respects_retry_after_header() -> None:
    """429 during poll: elapsed should advance by Retry-After amount."""
    # Return 429 once, then done.
    respx.get(POLL_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, json=DONE_RESPONSE),
        ]
    )
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    with patch("xai_cli.api.asyncio.sleep", side_effect=fake_sleep):
        async with _client() as client:
            result = await client.poll_video(VIDEO_ID, timeout_seconds=600)

    assert result["status"] == "done"
    # The first sleep must use the Retry-After value of 2
    assert sleep_calls[0] == pytest.approx(2.0)


@respx.mock
async def test_poll_video_on_status_callback_called() -> None:
    """on_status callback must be invoked for each status received."""
    statuses_seen: list[str] = []

    respx.get(POLL_URL).mock(
        side_effect=[
            httpx.Response(200, json={"id": VIDEO_ID, "status": "pending"}),
            httpx.Response(200, json=DONE_RESPONSE),
        ]
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        async with _client() as client:
            await client.poll_video(VIDEO_ID, on_status=statuses_seen.append)

    assert "pending" in statuses_seen
    assert "done" in statuses_seen


# ===========================================================================
# get_video_status
# ===========================================================================


@respx.mock
async def test_get_video_status_returns_raw_dict() -> None:
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID, "status": "pending"})
    )
    async with _client() as client:
        data = await client.get_video_status(VIDEO_ID)
    assert data == {"id": VIDEO_ID, "status": "pending"}


@respx.mock
async def test_get_video_status_done_returns_url() -> None:
    respx.get(POLL_URL).mock(return_value=httpx.Response(200, json=DONE_RESPONSE))
    async with _client() as client:
        data = await client.get_video_status(VIDEO_ID)
    assert data["url"] == "https://cdn.example.com/v.mp4"


@respx.mock
async def test_get_video_status_401_raises_auth_error() -> None:
    respx.get(POLL_URL).mock(return_value=httpx.Response(401, text="Unauthorized"))
    async with _client() as client:
        with pytest.raises(XAIAuthError):
            await client.get_video_status(VIDEO_ID)


@respx.mock
async def test_get_video_status_500_retries_3_times_raises_server_error() -> None:
    """_get_with_server_retry must attempt exactly 3 times before raising."""
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        async with _client() as client:
            with pytest.raises(XAIServerError):
                await client.get_video_status(VIDEO_ID)

    assert respx.calls.call_count == 3
    # Two inter-attempt sleeps for 3 total attempts
    assert mock_sleep.call_count == 2
