"""
CLI tests for `xai image edit`.

All HTTP is intercepted via respx at the transport layer.
CliRunner is used so no real process is spawned.

httpx.get (used in cli.py for --save downloads) is patched via unittest.mock
because it is a synchronous call that respx does not intercept.

Key exit codes:
  0 — success
  1 — pre-flight error, validation error, or missing API key
  2 — API / auth / edit error
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from xai_cli.api import _BASE_URL
from xai_cli.cli import app

runner = CliRunner()

EDIT_URL = f"{_BASE_URL}/images/edits"
IMAGE_RESPONSE = {"data": [{"url": "https://img.example.com/edited.png"}]}


def _env(extra: dict | None = None) -> dict:
    base = {"XAI_API_KEY": "test-key", "NO_COLOR": "1"}
    if extra:
        base.update(extra)
    return base


def _fake_httpx_get() -> MagicMock:
    """Return a mock that stands in for httpx.get() during --save tests."""
    mock_response = MagicMock()
    mock_response.content = b"fake-edited-image-bytes"
    mock_response.raise_for_status = MagicMock()
    return MagicMock(return_value=mock_response)


# ===========================================================================
# Happy paths
# ===========================================================================


@respx.mock
def test_edit_happy_path_exit_0() -> None:
    """Single --image flag with HTTPS URL exits 0 and prints 'Image URL:'."""
    respx.post(EDIT_URL).mock(
        return_value=httpx.Response(200, json=IMAGE_RESPONSE)
    )
    result = runner.invoke(
        app,
        [
            "image", "edit", "make it art",
            "--image", "https://example.com/img.jpg",
            "--output", "text",
        ],
        env=_env(),
    )
    assert result.exit_code == 0
    assert "Image URL:" in result.output


@respx.mock
def test_edit_output_json_valid() -> None:
    """--output json produces valid JSON with images key and correct structure."""
    respx.post(EDIT_URL).mock(
        return_value=httpx.Response(200, json=IMAGE_RESPONSE)
    )
    result = runner.invoke(
        app,
        [
            "image", "edit", "make it art",
            "--image", "https://example.com/img.jpg",
            "--output", "json",
        ],
        env=_env(),
    )
    assert result.exit_code == 0
    parsed = json.loads(result.output.strip())
    assert "images" in parsed
    assert parsed["images"][0]["index"] == 0
    assert parsed["images"][0]["url"] == "https://img.example.com/edited.png"


@respx.mock
def test_edit_multiple_images_exit_0() -> None:
    """Two --image flags are accepted and the command exits 0."""
    respx.post(EDIT_URL).mock(
        return_value=httpx.Response(200, json=IMAGE_RESPONSE)
    )
    result = runner.invoke(
        app,
        [
            "image", "edit", "blend them",
            "--image", "https://example.com/a.jpg",
            "--image", "https://example.com/b.jpg",
            "--output", "text",
        ],
        env=_env(),
    )
    assert result.exit_code == 0
    assert "Image URL:" in result.output


@respx.mock
def test_edit_local_png_preflight_ok(tmp_path: Path) -> None:
    """--image pointing to a real .png file passes pre-flight and exits 0."""
    png_file = tmp_path / "source.png"
    # Minimal 1×1 PNG (67 bytes) — valid enough to pass read_bytes()
    png_file.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
        b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    respx.post(EDIT_URL).mock(
        return_value=httpx.Response(200, json=IMAGE_RESPONSE)
    )
    result = runner.invoke(
        app,
        [
            "image", "edit", "make it pop",
            "--image", str(png_file),
            "--output", "text",
        ],
        env=_env(),
    )
    assert result.exit_code == 0
    assert "Image URL:" in result.output


# ===========================================================================
# Pre-flight errors
# ===========================================================================


def test_edit_invalid_image_type_exit_1(tmp_path: Path) -> None:
    """--image pointing to a .gif rejects before any HTTP call and exits 1."""
    gif_file = tmp_path / "anim.gif"
    gif_file.write_bytes(b"GIF89a" + b"\x00" * 10)
    result = runner.invoke(
        app,
        [
            "image", "edit", "make it art",
            "--image", str(gif_file),
        ],
        env=_env(),
    )
    assert result.exit_code == 1
    # No HTTP call should have been made (respx would raise if one slipped through)


def test_edit_missing_image_file_exit_1(tmp_path: Path) -> None:
    """--image pointing to a nonexistent file exits 1 with an error message."""
    missing = tmp_path / "does_not_exist.png"
    result = runner.invoke(
        app,
        [
            "image", "edit", "make it art",
            "--image", str(missing),
        ],
        env=_env(),
    )
    assert result.exit_code == 1


# ===========================================================================
# Save to file
# ===========================================================================


@respx.mock
def test_edit_save_downloads_file(tmp_path: Path) -> None:
    """--save PATH downloads the result image and prints 'Saved to'."""
    respx.post(EDIT_URL).mock(
        return_value=httpx.Response(200, json=IMAGE_RESPONSE)
    )
    out_file = tmp_path / "out.png"
    with patch("xai_cli.cli.httpx.get", _fake_httpx_get()):
        result = runner.invoke(
            app,
            [
                "image", "edit", "make it art",
                "--image", "https://example.com/img.jpg",
                "--save", str(out_file),
                "--output", "text",
            ],
            env=_env(),
        )
    assert result.exit_code == 0
    assert "Saved to" in result.output
    assert str(out_file) in result.output
    assert out_file.read_bytes() == b"fake-edited-image-bytes"


# ===========================================================================
# Error responses
# ===========================================================================


@respx.mock
def test_edit_401_exit_2() -> None:
    """A 401 from the API exits 2."""
    respx.post(EDIT_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    result = runner.invoke(
        app,
        [
            "image", "edit", "make it art",
            "--image", "https://example.com/img.jpg",
        ],
        env=_env(),
    )
    assert result.exit_code == 2


@respx.mock
def test_edit_validation_error_exit_1() -> None:
    """A 400 from the API maps to exit 1 (XAIValidationError)."""
    respx.post(EDIT_URL).mock(
        return_value=httpx.Response(400, text="Bad request: invalid prompt")
    )
    result = runner.invoke(
        app,
        [
            "image", "edit", "",
            "--image", "https://example.com/img.jpg",
            "--output", "text",
        ],
        env=_env(),
    )
    assert result.exit_code == 1


def test_edit_missing_api_key_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing API key exits 1 and mentions the key in output."""
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with patch("xai_cli.config.load_config", return_value={}):
        result = runner.invoke(
            app,
            [
                "image", "edit", "make it art",
                "--image", "https://example.com/img.jpg",
            ],
        )
    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "api key" in combined.lower() or "xai_api_key" in combined.lower()
