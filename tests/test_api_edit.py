"""
Unit tests for XAIClient.edit_image() — all HTTP interactions mocked via respx.

Key facts about the real implementation:
- edit_image raises ValueError before any HTTP call when images is empty or has >5 items
- Uses _request_with_server_retry (same retry path as generate_image)
- Raises ImageEditError when response data is empty or missing
- Optional field aspect_ratio is omitted from body when None
- image array entries use {"type": "image_url", "image_url": {"url": <img>}} wrapper
"""

import json

import httpx
import pytest
import respx

from xai_cli.api import XAIClient, _BASE_URL
from xai_cli.exceptions import (
    ImageEditError,
    XAIAuthError,
    XAIValidationError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EDIT_URL = f"{_BASE_URL}/images/edits"
IMAGE_RESPONSE = {"data": [{"url": "https://img.example.com/edited.png"}]}


def _client() -> XAIClient:
    return XAIClient("test-key")


pytestmark = pytest.mark.asyncio


# ===========================================================================
# Happy paths
# ===========================================================================


@respx.mock
async def test_edit_image_happy_path() -> None:
    """Single image POST returns the data list."""
    respx.post(EDIT_URL).mock(
        return_value=httpx.Response(200, json=IMAGE_RESPONSE)
    )
    async with _client() as client:
        result = await client.edit_image(
            prompt="make it art",
            images=["https://example.com/img.jpg"],
        )
    assert len(result) == 1
    assert result[0]["url"] == "https://img.example.com/edited.png"


@respx.mock
async def test_edit_image_request_body_structure() -> None:
    """Request body must have image array with type/image_url wrapper, prompt, model."""

    def assert_body(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["prompt"] == "make it pop"
        assert body["model"] == "grok-imagine-image"
        assert isinstance(body["image"], list)
        assert len(body["image"]) == 1
        entry = body["image"][0]
        assert entry["type"] == "image_url"
        assert entry["image_url"]["url"] == "https://example.com/img.jpg"
        return httpx.Response(200, json=IMAGE_RESPONSE)

    respx.post(EDIT_URL).mock(side_effect=assert_body)
    async with _client() as client:
        await client.edit_image(
            prompt="make it pop",
            images=["https://example.com/img.jpg"],
        )


@respx.mock
async def test_edit_image_multiple_images() -> None:
    """Two images must produce an image array with exactly two entries."""

    def assert_two_entries(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert len(body["image"]) == 2
        assert body["image"][0]["image_url"]["url"] == "https://example.com/a.jpg"
        assert body["image"][1]["image_url"]["url"] == "https://example.com/b.jpg"
        return httpx.Response(200, json=IMAGE_RESPONSE)

    respx.post(EDIT_URL).mock(side_effect=assert_two_entries)
    async with _client() as client:
        result = await client.edit_image(
            prompt="blend them",
            images=["https://example.com/a.jpg", "https://example.com/b.jpg"],
        )
    assert len(result) == 1


@respx.mock
async def test_edit_image_aspect_ratio_included() -> None:
    """aspect_ratio must appear in the body when provided."""

    def assert_aspect_ratio(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["aspect_ratio"] == "16:9"
        return httpx.Response(200, json=IMAGE_RESPONSE)

    respx.post(EDIT_URL).mock(side_effect=assert_aspect_ratio)
    async with _client() as client:
        await client.edit_image(
            prompt="widescreen edit",
            images=["https://example.com/img.jpg"],
            aspect_ratio="16:9",
        )


@respx.mock
async def test_edit_image_aspect_ratio_omitted() -> None:
    """aspect_ratio must NOT appear in the body when not provided."""

    def assert_no_aspect_ratio(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "aspect_ratio" not in body
        return httpx.Response(200, json=IMAGE_RESPONSE)

    respx.post(EDIT_URL).mock(side_effect=assert_no_aspect_ratio)
    async with _client() as client:
        await client.edit_image(
            prompt="simple edit",
            images=["https://example.com/img.jpg"],
        )


# ===========================================================================
# Pre-network validation — no HTTP calls expected
# ===========================================================================


async def test_edit_image_zero_images_raises_value_error() -> None:
    """images=[] must raise ValueError before any HTTP call is made."""
    async with _client() as client:
        with pytest.raises(ValueError):
            await client.edit_image(prompt="test", images=[])


async def test_edit_image_six_images_raises_value_error() -> None:
    """images with 6 entries must raise ValueError before any HTTP call is made."""
    async with _client() as client:
        with pytest.raises(ValueError):
            await client.edit_image(prompt="test", images=["x"] * 6)


# ===========================================================================
# Error states — empty / missing data
# ===========================================================================


@respx.mock
async def test_edit_image_empty_data_raises_edit_error() -> None:
    """A 200 with data=[] must raise ImageEditError."""
    respx.post(EDIT_URL).mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    async with _client() as client:
        with pytest.raises(ImageEditError):
            await client.edit_image(
                prompt="test",
                images=["https://example.com/img.jpg"],
            )


# ===========================================================================
# HTTP error mapping
# ===========================================================================


@respx.mock
async def test_edit_image_401_raises_auth_error() -> None:
    respx.post(EDIT_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    async with _client() as client:
        with pytest.raises(XAIAuthError):
            await client.edit_image(
                prompt="test",
                images=["https://example.com/img.jpg"],
            )


@respx.mock
async def test_edit_image_400_raises_validation_error() -> None:
    respx.post(EDIT_URL).mock(
        return_value=httpx.Response(400, text="Bad request: invalid prompt")
    )
    async with _client() as client:
        with pytest.raises(XAIValidationError):
            await client.edit_image(
                prompt="",
                images=["https://example.com/img.jpg"],
            )
