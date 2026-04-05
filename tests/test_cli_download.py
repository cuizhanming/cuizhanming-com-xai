"""
CLI tests for `xai video download`.

Exit codes:
  0 — downloaded successfully
  1 — generation not yet complete
  2 — API / network error
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from xai_cli.api import _BASE_URL
from xai_cli.cli import app

runner = CliRunner()

VIDEO_ID = "vg-dl-001"
POLL_URL = f"{_BASE_URL}/videos/{VIDEO_ID}"
VIDEO_CONTENT = b"FAKE_MP4_BYTES"
VIDEO_DOWNLOAD_URL = "https://cdn.example.com/output.mp4"


def _env(extra: dict | None = None) -> dict:
    base = {"XAI_API_KEY": "test-key", "NO_COLOR": "1"}
    if extra:
        base.update(extra)
    return base


def _done_status_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": VIDEO_ID,
            "status": "done",
            "url": VIDEO_DOWNLOAD_URL,
        },
    )


# ===========================================================================
# Happy path — done, default output path
# ===========================================================================


@respx.mock
def test_download_done_saves_file_exit_0(tmp_path: Path) -> None:
    """Status is done — file must be downloaded and saved."""
    out_file = tmp_path / f"{VIDEO_ID}.mp4"

    respx.get(POLL_URL).mock(return_value=_done_status_response())
    respx.get(VIDEO_DOWNLOAD_URL).mock(
        return_value=httpx.Response(
            200,
            content=VIDEO_CONTENT,
            headers={"content-length": str(len(VIDEO_CONTENT))},
        )
    )

    result = runner.invoke(
        app,
        ["video", "download", VIDEO_ID, "--output", str(out_file)],
        env=_env(),
    )

    assert result.exit_code == 0
    assert out_file.exists()
    assert out_file.read_bytes() == VIDEO_CONTENT
    assert str(out_file) in result.output or out_file.name in result.output


@respx.mock
def test_download_default_output_path_is_id_dot_mp4(tmp_path: Path) -> None:
    """When --output is omitted the file should be saved as <id>.mp4."""
    respx.get(POLL_URL).mock(return_value=_done_status_response())
    respx.get(VIDEO_DOWNLOAD_URL).mock(
        return_value=httpx.Response(200, content=VIDEO_CONTENT)
    )

    # Run from tmp_path so the default file lands there, not the repo root
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        result = runner.invoke(
            app,
            ["video", "download", VIDEO_ID],
            env=_env(),
        )

    # The CLI should report the filename in its success message
    assert result.exit_code == 0
    assert f"{VIDEO_ID}.mp4" in result.output


# ===========================================================================
# Generation not yet complete
# ===========================================================================


@respx.mock
def test_download_pending_exit_1() -> None:
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200, json={"id": VIDEO_ID, "status": "pending"}
        )
    )

    result = runner.invoke(
        app, ["video", "download", VIDEO_ID], env=_env()
    )

    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "not yet complete" in combined.lower()


@respx.mock
def test_download_failed_status_exit_1() -> None:
    """Any non-done status should exit 1 with a message."""
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200, json={"id": VIDEO_ID, "status": "failed"}
        )
    )

    result = runner.invoke(
        app, ["video", "download", VIDEO_ID], env=_env()
    )

    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "not yet complete" in combined.lower()


# ===========================================================================
# Custom --output path
# ===========================================================================


@respx.mock
def test_download_custom_output_path(tmp_path: Path) -> None:
    custom = tmp_path / "my_video.mp4"

    respx.get(POLL_URL).mock(return_value=_done_status_response())
    respx.get(VIDEO_DOWNLOAD_URL).mock(
        return_value=httpx.Response(200, content=VIDEO_CONTENT)
    )

    result = runner.invoke(
        app,
        ["video", "download", VIDEO_ID, "--output", str(custom)],
        env=_env(),
    )

    assert result.exit_code == 0
    assert custom.exists()
    assert custom.read_bytes() == VIDEO_CONTENT


# ===========================================================================
# Status API error
# ===========================================================================


@respx.mock
def test_download_status_api_401_exit_2() -> None:
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    result = runner.invoke(
        app, ["video", "download", VIDEO_ID], env=_env()
    )

    assert result.exit_code == 2


# ===========================================================================
# Download network error
# ===========================================================================


@respx.mock
def test_download_network_error_during_download_exit_2(tmp_path: Path) -> None:
    """If the video URL itself fails, exit code must be 2."""
    out_file = tmp_path / f"{VIDEO_ID}.mp4"

    respx.get(POLL_URL).mock(return_value=_done_status_response())
    respx.get(VIDEO_DOWNLOAD_URL).mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    result = runner.invoke(
        app,
        ["video", "download", VIDEO_ID, "--output", str(out_file)],
        env=_env(),
    )

    assert result.exit_code == 2
