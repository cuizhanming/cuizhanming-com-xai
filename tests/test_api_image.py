"""
Unit tests for XAIClient.generate_image() — all HTTP interactions mocked via respx.

Key facts about the real implementation:
- generate_image uses _request_with_server_retry (3 attempts for 5xx)
- No polling involved — single POST, returns data list immediately
- Raises ImageGenerationError when data is empty or missing from response
- Optional fields aspect_ratio and resolution are omitted from body when None
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from xai_cli.api import XAIClient, _BASE_URL
from xai_cli.exceptions import (
    ImageGenerationError,
    XAIAuthError,
    XAIServerError,
    XAIValidationError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

IMAGE_URL = f"{_BASE_URL}/images/generations"


def _client() -> XAIClient:
    return XAIClient("test-key")


pytestmark = pytest.mark.asyncio


# ===========================================================================
# Happy paths
# ===========================================================================


@respx.mock
async def test_generate_image_happy_path() -> None:
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(
            200, json={"data": [{"url": "https://img.example.com/a.png"}]}
        )
    )
    async with _client() as client:
        result = await client.generate_image(prompt="a cat on a beach")
    assert len(result) == 1
    assert result[0]["url"] == "https://img.example.com/a.png"


@respx.mock
async def test_generate_image_multiple_n() -> None:
    """n=3 must appear in the request body and the full data list is returned."""
    images = [
        {"url": f"https://img.example.com/{i}.png"} for i in range(3)
    ]

    def assert_n_in_body(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["n"] == 3
        return httpx.Response(200, json={"data": images})

    respx.post(IMAGE_URL).mock(side_effect=assert_n_in_body)
    async with _client() as client:
        result = await client.generate_image(prompt="three landscapes", n=3)
    assert len(result) == 3


@respx.mock
async def test_generate_image_optional_fields_included() -> None:
    """aspect_ratio and resolution must appear in the body when provided."""

    def assert_optional_fields(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["aspect_ratio"] == "16:9"
        assert body["resolution"] == "2k"
        return httpx.Response(
            200, json={"data": [{"url": "https://img.example.com/a.png"}]}
        )

    respx.post(IMAGE_URL).mock(side_effect=assert_optional_fields)
    async with _client() as client:
        await client.generate_image(
            prompt="wide shot", aspect_ratio="16:9", resolution="2k"
        )


@respx.mock
async def test_generate_image_optional_fields_omitted() -> None:
    """aspect_ratio and resolution must NOT appear in the body when not provided."""

    def assert_no_optional_fields(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "aspect_ratio" not in body
        assert "resolution" not in body
        return httpx.Response(
            200, json={"data": [{"url": "https://img.example.com/a.png"}]}
        )

    respx.post(IMAGE_URL).mock(side_effect=assert_no_optional_fields)
    async with _client() as client:
        await client.generate_image(prompt="a simple scene")


# ===========================================================================
# Error states — empty / missing data
# ===========================================================================


@respx.mock
async def test_generate_image_empty_data_raises_error() -> None:
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    async with _client() as client:
        with pytest.raises(ImageGenerationError):
            await client.generate_image(prompt="test")


@respx.mock
async def test_generate_image_missing_data_key_raises_error() -> None:
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(200, json={})
    )
    async with _client() as client:
        with pytest.raises(ImageGenerationError):
            await client.generate_image(prompt="test")


# ===========================================================================
# HTTP error mapping
# ===========================================================================


@respx.mock
async def test_generate_image_401_raises_auth_error() -> None:
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    async with _client() as client:
        with pytest.raises(XAIAuthError):
            await client.generate_image(prompt="test")


@respx.mock
async def test_generate_image_400_raises_validation_error() -> None:
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(400, text="Bad request: invalid prompt")
    )
    async with _client() as client:
        with pytest.raises(XAIValidationError):
            await client.generate_image(prompt="")


@respx.mock
async def test_generate_image_500_retries_raises_server_error() -> None:
    """generate_image retries up to 3 times on 5xx before raising XAIServerError."""
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )
    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        async with _client() as client:
            with pytest.raises(XAIServerError):
                await client.generate_image(prompt="test")
    assert respx.calls.call_count == 3
