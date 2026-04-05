"""
CLI tests for `xai video generate`.

All HTTP is intercepted via respx at the transport layer.
CliRunner is used so no real process is spawned.

Key exit codes:
  0 — success
  1 — pre-flight error (bad image arg) or missing API key
  2 — API / generation error
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from xai_cli.api import _BASE_URL
from xai_cli.cli import app

runner = CliRunner()

GENERATE_URL = f"{_BASE_URL}/videos/generations"
VIDEO_ID = "vg-cli-001"
POLL_URL = f"{_BASE_URL}/videos/{VIDEO_ID}"
DONE_RESPONSE = {
    "id": VIDEO_ID,
    "status": "done",
    "url": "https://cdn.example.com/output.mp4",
}


def _env(extra: dict | None = None) -> dict:
    base = {"XAI_API_KEY": "test-key", "NO_COLOR": "1"}
    if extra:
        base.update(extra)
    return base


# ===========================================================================
# Happy paths
# ===========================================================================


@respx.mock
def test_generate_happy_path_exit_0() -> None:
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID})
    )
    respx.get(POLL_URL).mock(return_value=httpx.Response(200, json=DONE_RESPONSE))

    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        result = runner.invoke(
            app,
            ["video", "generate", "a beautiful sunset"],
            env=_env(),
        )

    assert result.exit_code == 0
    assert "https://cdn.example.com/output.mp4" in result.output


@respx.mock
def test_generate_with_https_image_url_exit_0() -> None:
    """--image with an HTTPS URL must reach the API (no pre-flight rejection)."""
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID})
    )
    respx.get(POLL_URL).mock(return_value=httpx.Response(200, json=DONE_RESPONSE))

    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        result = runner.invoke(
            app,
            [
                "video",
                "generate",
                "a sunset",
                "--image",
                "https://example.com/frame.jpg",
            ],
            env=_env(),
        )

    assert result.exit_code == 0


@respx.mock
def test_generate_with_local_png_exit_0(tmp_path: Path) -> None:
    """--image pointing to a real local PNG should succeed."""
    img = tmp_path / "frame.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)

    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID})
    )
    respx.get(POLL_URL).mock(return_value=httpx.Response(200, json=DONE_RESPONSE))

    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        result = runner.invoke(
            app,
            ["video", "generate", "a sunset", "--image", str(img)],
            env=_env(),
        )

    assert result.exit_code == 0


# ===========================================================================
# Pre-flight image errors — exit 1, no HTTP calls made
# ===========================================================================


@respx.mock
def test_generate_gif_image_exit_1_no_http_calls(tmp_path: Path) -> None:
    img = tmp_path / "bad.gif"
    img.write_bytes(b"GIF89a")

    result = runner.invoke(
        app,
        ["video", "generate", "prompt", "--image", str(img)],
        env=_env(),
    )

    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "unsupported image type" in combined.lower()
    # No HTTP calls should have been made
    assert respx.calls.call_count == 0


@respx.mock
def test_generate_missing_image_file_exit_1_no_http_calls(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jpg"  # deliberately not created

    result = runner.invoke(
        app,
        ["video", "generate", "prompt", "--image", str(missing)],
        env=_env(),
    )

    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "not found" in combined.lower() or "no such file" in combined.lower() or "filenotfounderror" in combined.lower()
    assert respx.calls.call_count == 0


@respx.mock
def test_generate_http_image_url_exit_1_no_http_calls() -> None:
    result = runner.invoke(
        app,
        [
            "video",
            "generate",
            "prompt",
            "--image",
            "http://example.com/img.jpg",
        ],
        env=_env(),
    )

    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "https" in combined.lower()
    assert respx.calls.call_count == 0


# ===========================================================================
# Output format
# ===========================================================================


@respx.mock
def test_generate_output_json_is_valid_json() -> None:
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID})
    )
    respx.get(POLL_URL).mock(return_value=httpx.Response(200, json=DONE_RESPONSE))

    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        result = runner.invoke(
            app,
            ["video", "generate", "a sunset", "--output", "json"],
            env=_env(),
        )

    assert result.exit_code == 0
    parsed = json.loads(result.output.strip())
    assert parsed["id"] == VIDEO_ID
    assert parsed["status"] == "done"
    assert parsed["url"] == "https://cdn.example.com/output.mp4"


@respx.mock
def test_generate_output_text_contains_url() -> None:
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID})
    )
    respx.get(POLL_URL).mock(return_value=httpx.Response(200, json=DONE_RESPONSE))

    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        result = runner.invoke(
            app,
            ["video", "generate", "a sunset", "--output", "text"],
            env=_env(),
        )

    assert result.exit_code == 0
    assert "https://cdn.example.com/output.mp4" in result.output
    # Must not accidentally emit raw JSON
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output.strip())


# ===========================================================================
# Missing API key
# ===========================================================================


def test_generate_missing_api_key_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    # Ensure config file has no api_key by patching load_config to return empty
    with patch("xai_cli.config.load_config", return_value={}):
        result = runner.invoke(
            app,
            ["video", "generate", "a sunset"],
            # No env dict — key intentionally absent
        )

    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "api key" in combined.lower() or "xai_api_key" in combined.lower()


# ===========================================================================
# API error responses
# ===========================================================================


@respx.mock
def test_generate_api_401_exit_2() -> None:
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        result = runner.invoke(
            app,
            ["video", "generate", "a sunset"],
            env=_env(),
        )

    assert result.exit_code == 2


@respx.mock
def test_generate_generation_failed_exit_2() -> None:
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID})
    )
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": VIDEO_ID,
                "status": "failed",
                "error": {"code": "policy", "message": "rejected"},
            },
        )
    )

    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        result = runner.invoke(
            app,
            ["video", "generate", "a sunset"],
            env=_env(),
        )

    assert result.exit_code == 2


@respx.mock
def test_generate_generation_expired_exit_2() -> None:
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID})
    )
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200,
            json={"id": VIDEO_ID, "status": "expired"},
        )
    )

    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        result = runner.invoke(
            app,
            ["video", "generate", "a sunset"],
            env=_env(),
        )

    assert result.exit_code == 2


@respx.mock
def test_generate_polling_timeout_exit_2() -> None:
    """timeout_seconds=0 forces an immediate VideoGenerationTimeoutError."""
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID})
    )
    # Poll URL registered so respx does not raise unmatched; may not be called.
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(200, json={"id": VIDEO_ID, "status": "pending"})
    )

    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        result = runner.invoke(
            app,
            ["video", "generate", "a sunset", "--timeout", "0"],
            env=_env(),
        )

    assert result.exit_code == 2
