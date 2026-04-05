"""
CLI tests for `xai image generate`.

All HTTP is intercepted via respx at the transport layer.
CliRunner is used so no real process is spawned.

httpx.get (used in cli.py for --save downloads) is patched via unittest.mock
because it is a synchronous call that respx does not intercept.

Key exit codes:
  0 — success
  1 — pre-flight error or missing API key
  2 — API / generation error
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from xai_cli.api import _BASE_URL
from xai_cli.cli import app

runner = CliRunner()

IMAGE_URL = f"{_BASE_URL}/images/generations"

_SINGLE_IMAGE_RESPONSE = {
    "data": [{"url": "https://img.example.com/result.png"}]
}
_TWO_IMAGE_RESPONSE = {
    "data": [
        {"url": "https://img.example.com/result-1.png"},
        {"url": "https://img.example.com/result-2.png"},
    ]
}


def _env(extra: dict | None = None) -> dict:
    base = {"XAI_API_KEY": "test-key", "NO_COLOR": "1"}
    if extra:
        base.update(extra)
    return base


def _fake_httpx_get() -> MagicMock:
    """Return a mock that stands in for httpx.get() during --save tests."""
    mock_response = MagicMock()
    mock_response.content = b"fake-image-bytes"
    mock_response.raise_for_status = MagicMock()
    mock_get = MagicMock(return_value=mock_response)
    return mock_get


# ===========================================================================
# Happy paths
# ===========================================================================


@respx.mock
def test_image_generate_happy_path_exit_0() -> None:
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(200, json=_SINGLE_IMAGE_RESPONSE)
    )
    # CliRunner uses a non-TTY stdout, so --output must be explicit for text mode.
    result = runner.invoke(
        app,
        ["image", "generate", "a cat on a beach", "--output", "text"],
        env=_env(),
    )
    assert result.exit_code == 0
    assert "Image URL:" in result.output


@respx.mock
def test_image_generate_output_json_valid() -> None:
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(200, json=_SINGLE_IMAGE_RESPONSE)
    )
    result = runner.invoke(
        app,
        ["image", "generate", "a cat on a beach", "--output", "json"],
        env=_env(),
    )
    assert result.exit_code == 0
    parsed = json.loads(result.output.strip())
    assert "images" in parsed
    assert parsed["images"][0]["index"] == 0
    assert parsed["images"][0]["url"] == "https://img.example.com/result.png"


@respx.mock
def test_image_generate_output_text_contains_url() -> None:
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(200, json=_SINGLE_IMAGE_RESPONSE)
    )
    result = runner.invoke(
        app,
        ["image", "generate", "a cat on a beach", "--output", "text"],
        env=_env(),
    )
    assert result.exit_code == 0
    assert "https://img.example.com/result.png" in result.output
    # Must not accidentally emit raw JSON
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output.strip())


@respx.mock
def test_image_generate_multiple_n_exit_0() -> None:
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(200, json=_TWO_IMAGE_RESPONSE)
    )
    result = runner.invoke(
        app,
        ["image", "generate", "two landscapes", "--n", "2", "--output", "text"],
        env=_env(),
    )
    assert result.exit_code == 0
    assert result.output.count("Image URL:") == 2


# ===========================================================================
# Save to file
# ===========================================================================


@respx.mock
def test_image_generate_save_single_image(tmp_path: Path) -> None:
    """--save with n=1 writes the file and prints 'Saved to <path>'.

    For n=1, cli.py uses save_path directly so the full absolute path is
    preserved. Force --output text because CliRunner is not a TTY.
    """
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(200, json=_SINGLE_IMAGE_RESPONSE)
    )
    out_file = tmp_path / "out.png"
    with patch("xai_cli.cli.httpx.get", _fake_httpx_get()):
        result = runner.invoke(
            app,
            [
                "image", "generate", "a portrait",
                "--save", str(out_file),
                "--output", "text",
            ],
            env=_env(),
        )
    assert result.exit_code == 0
    assert "Saved to" in result.output
    assert str(out_file) in result.output
    assert out_file.read_bytes() == b"fake-image-bytes"


@respx.mock
def test_image_generate_save_multi_image_naming(tmp_path: Path) -> None:
    """--save foo.png with n=2 names the outputs foo-1.png and foo-2.png.

    cli.py derives the numbered paths from stem + suffix only (the parent
    directory is not preserved for n>1), so we assert on the name pattern
    reported in the output rather than checking file existence at tmp_path.
    Use --output json so we can parse the exact paths the CLI reports.
    """
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(200, json=_TWO_IMAGE_RESPONSE)
    )
    with patch("xai_cli.cli.httpx.get", _fake_httpx_get()):
        result = runner.invoke(
            app,
            [
                "image", "generate", "two portraits",
                "--n", "2",
                "--save", "img.png",
                "--output", "json",
            ],
            env=_env(),
        )
    assert result.exit_code == 0
    parsed = json.loads(result.output.strip())
    assert "saved" in parsed
    saved = parsed["saved"]
    assert len(saved) == 2
    assert saved[0].endswith("img-1.png")
    assert saved[1].endswith("img-2.png")


# ===========================================================================
# Error responses
# ===========================================================================


@respx.mock
def test_image_generate_401_exit_2() -> None:
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    result = runner.invoke(
        app,
        ["image", "generate", "test"],
        env=_env(),
    )
    assert result.exit_code == 2


@respx.mock
def test_image_generate_validation_error_exit_1() -> None:
    respx.post(IMAGE_URL).mock(
        return_value=httpx.Response(400, text="Bad request: invalid prompt")
    )
    result = runner.invoke(
        app,
        ["image", "generate", ""],
        env=_env(),
    )
    assert result.exit_code == 1


def test_image_generate_missing_api_key_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with patch("xai_cli.config.load_config", return_value={}):
        result = runner.invoke(
            app,
            ["image", "generate", "a cat"],
        )
    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "api key" in combined.lower() or "xai_api_key" in combined.lower()
