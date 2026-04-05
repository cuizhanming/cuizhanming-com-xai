"""
Unit tests for XAIClient batch methods — all HTTP interactions mocked via respx.

Key facts about the real implementation:
- create_image_batch uses _request_with_server_retry (POST /batches)
- add_image_batch_request uses _request_with_server_retry (POST /batches/{id}/requests)
- get_batch_status uses _get_with_server_retry (GET /batches/{id})
- poll_batch uses _get_with_server_retry with 429/timeout handling
- get_batch_results uses _get_with_server_retry with optional ?after cursor
- Terminal batch state: num_pending == 0
- asyncio.sleep is patched to a no-op so tests run instantly
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from xai_cli.api import XAIClient, _BASE_URL
from xai_cli.exceptions import (
    ImageBatchTimeoutError,
    XAIAuthError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BATCHES_URL = f"{_BASE_URL}/batches"
BATCH_ID = "batch-test-001"
STATUS_URL = f"{_BASE_URL}/batches/{BATCH_ID}"
REQUESTS_URL = f"{_BASE_URL}/batches/{BATCH_ID}/requests"
RESULTS_URL = f"{_BASE_URL}/batches/{BATCH_ID}/results"


def _client() -> XAIClient:
    return XAIClient("test-key")


pytestmark = pytest.mark.asyncio


# ===========================================================================
# create_image_batch
# ===========================================================================


@respx.mock
async def test_create_batch_happy_path() -> None:
    """POST /batches returns {"id": "..."} → method returns the id string."""
    respx.post(BATCHES_URL).mock(
        return_value=httpx.Response(200, json={"id": BATCH_ID})
    )
    async with _client() as client:
        result = await client.create_image_batch()
    assert result == BATCH_ID


@respx.mock
async def test_create_batch_with_name_includes_name_in_body() -> None:
    """When name= is provided the request body must contain "name"."""

    def assert_body_has_name(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "name" in body
        assert body["name"] == "my-batch"
        return httpx.Response(200, json={"id": BATCH_ID})

    respx.post(BATCHES_URL).mock(side_effect=assert_body_has_name)
    async with _client() as client:
        result = await client.create_image_batch(name="my-batch")
    assert result == BATCH_ID


@respx.mock
async def test_create_batch_without_name_omits_name_from_body() -> None:
    """When name=None the request body must NOT contain the "name" key."""

    def assert_no_name(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "name" not in body
        return httpx.Response(200, json={"id": BATCH_ID})

    respx.post(BATCHES_URL).mock(side_effect=assert_no_name)
    async with _client() as client:
        await client.create_image_batch(name=None)


@respx.mock
async def test_create_batch_401_raises_auth_error() -> None:
    respx.post(BATCHES_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    async with _client() as client:
        with pytest.raises(XAIAuthError):
            await client.create_image_batch()


# ===========================================================================
# add_image_batch_request
# ===========================================================================


@respx.mock
async def test_add_batch_request_happy_path() -> None:
    """200 response → no exception raised."""
    respx.post(REQUESTS_URL).mock(
        return_value=httpx.Response(200, json={})
    )
    async with _client() as client:
        # Should complete without raising
        await client.add_image_batch_request(
            batch_id=BATCH_ID,
            batch_request_id="req-0",
            prompt="a sunset over the mountains",
        )


@respx.mock
async def test_add_batch_request_body_structure() -> None:
    """Body must nest prompt inside batch_request.images.generations,
    and optional aspect_ratio must be present when provided."""

    def assert_body(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["batch_request_id"] == "req-0"
        generations = body["batch_request"]["images"]["generations"]
        assert generations["prompt"] == "a sunset"
        assert generations["model"] == "grok-imagine-image"
        assert generations["n"] == 1
        assert generations["aspect_ratio"] == "16:9"
        return httpx.Response(200, json={})

    respx.post(REQUESTS_URL).mock(side_effect=assert_body)
    async with _client() as client:
        await client.add_image_batch_request(
            batch_id=BATCH_ID,
            batch_request_id="req-0",
            prompt="a sunset",
            aspect_ratio="16:9",
        )


@respx.mock
async def test_add_batch_request_optional_fields_omitted() -> None:
    """Without aspect_ratio/resolution the nested generations dict must not contain them."""

    def assert_no_optional(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        generations = body["batch_request"]["images"]["generations"]
        assert "aspect_ratio" not in generations
        assert "resolution" not in generations
        return httpx.Response(200, json={})

    respx.post(REQUESTS_URL).mock(side_effect=assert_no_optional)
    async with _client() as client:
        await client.add_image_batch_request(
            batch_id=BATCH_ID,
            batch_request_id="req-0",
            prompt="a mountain lake",
        )


# ===========================================================================
# get_batch_status
# ===========================================================================


@respx.mock
async def test_get_batch_status_returns_dict() -> None:
    status_payload = {
        "id": BATCH_ID,
        "num_requests": 5,
        "num_pending": 3,
        "num_success": 2,
        "num_error": 0,
        "num_cancelled": 0,
    }
    respx.get(STATUS_URL).mock(
        return_value=httpx.Response(200, json=status_payload)
    )
    async with _client() as client:
        data = await client.get_batch_status(BATCH_ID)
    assert data == status_payload
    assert data["num_pending"] == 3


@respx.mock
async def test_get_batch_status_401_raises_auth_error() -> None:
    respx.get(STATUS_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    async with _client() as client:
        with pytest.raises(XAIAuthError):
            await client.get_batch_status(BATCH_ID)


# ===========================================================================
# poll_batch
# ===========================================================================


@respx.mock
async def test_poll_batch_completes_when_pending_zero() -> None:
    """First response has num_pending=1, second has num_pending=0 → returns second dict."""
    pending_response = {"id": BATCH_ID, "num_pending": 1, "num_success": 0, "num_error": 0}
    complete_response = {"id": BATCH_ID, "num_pending": 0, "num_success": 1, "num_error": 0}

    respx.get(STATUS_URL).mock(
        side_effect=[
            httpx.Response(200, json=pending_response),
            httpx.Response(200, json=complete_response),
        ]
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        async with _client() as client:
            result = await client.poll_batch(BATCH_ID)

    assert result["num_pending"] == 0
    assert result["num_success"] == 1


@respx.mock
async def test_poll_batch_calls_on_status_callback() -> None:
    """on_status must be invoked with each status dict received."""
    calls: list[dict] = []
    pending_response = {"id": BATCH_ID, "num_pending": 2, "num_success": 0, "num_error": 0}
    complete_response = {"id": BATCH_ID, "num_pending": 0, "num_success": 2, "num_error": 0}

    respx.get(STATUS_URL).mock(
        side_effect=[
            httpx.Response(200, json=pending_response),
            httpx.Response(200, json=complete_response),
        ]
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        async with _client() as client:
            await client.poll_batch(BATCH_ID, on_status=calls.append)

    assert len(calls) == 2
    assert calls[0]["num_pending"] == 2
    assert calls[1]["num_pending"] == 0


@respx.mock
async def test_poll_batch_timeout_raises_error() -> None:
    """timeout_seconds=0 causes the loop to never enter → ImageBatchTimeoutError raised."""
    respx.get(STATUS_URL).mock(
        return_value=httpx.Response(
            200, json={"id": BATCH_ID, "num_pending": 5, "num_success": 0, "num_error": 0}
        )
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        async with _client() as client:
            with pytest.raises(ImageBatchTimeoutError) as exc_info:
                await client.poll_batch(BATCH_ID, timeout_seconds=0)

    assert exc_info.value.batch_id == BATCH_ID


@respx.mock
async def test_poll_batch_respects_retry_after_on_429() -> None:
    """429 with Retry-After: 5 → asyncio.sleep called with 5.0, then poll completes."""
    complete_response = {"id": BATCH_ID, "num_pending": 0, "num_success": 1, "num_error": 0}
    sleep_calls: list[float] = []

    respx.get(STATUS_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "5"}),
            httpx.Response(200, json=complete_response),
        ]
    )

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    with patch("xai_cli.api.asyncio.sleep", side_effect=fake_sleep):
        async with _client() as client:
            result = await client.poll_batch(BATCH_ID, timeout_seconds=3600)

    assert result["num_pending"] == 0
    assert sleep_calls[0] == pytest.approx(5.0)


# ===========================================================================
# get_batch_results
# ===========================================================================


@respx.mock
async def test_get_batch_results_returns_dict() -> None:
    results_payload = {
        "results": [
            {
                "batch_request_id": "req-0",
                "status": "succeeded",
                "result": {"data": [{"url": "https://img.example.com/0.png"}]},
            }
        ],
        "has_more": False,
        "last_id": None,
    }
    respx.get(RESULTS_URL).mock(
        return_value=httpx.Response(200, json=results_payload)
    )
    async with _client() as client:
        data = await client.get_batch_results(BATCH_ID)

    assert data["has_more"] is False
    assert len(data["results"]) == 1
    assert data["results"][0]["batch_request_id"] == "req-0"


@respx.mock
async def test_get_batch_results_with_after_cursor() -> None:
    """When after= is given the request URL must include ?after=<cursor>."""
    cursor = "cursor-123"

    def assert_cursor_in_url(request: httpx.Request) -> httpx.Response:
        assert f"after={cursor}" in str(request.url)
        return httpx.Response(
            200,
            json={"results": [], "has_more": False, "last_id": None},
        )

    respx.get(f"{RESULTS_URL}?after={cursor}").mock(side_effect=assert_cursor_in_url)
    async with _client() as client:
        data = await client.get_batch_results(BATCH_ID, after=cursor)

    assert data["has_more"] is False
