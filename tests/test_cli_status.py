"""
CLI tests for `xai video status`.

Exit codes:
  0 — success (any status returned from API)
  2 — API error
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from xai_cli.api import _BASE_URL
from xai_cli.cli import app

runner = CliRunner()

VIDEO_ID = "vg-status-001"
POLL_URL = f"{_BASE_URL}/videos/{VIDEO_ID}"


def _env(extra: dict | None = None) -> dict:
    base = {"XAI_API_KEY": "test-key", "NO_COLOR": "1"}
    if extra:
        base.update(extra)
    return base


# ===========================================================================
# Pending status
# ===========================================================================


@respx.mock
def test_status_pending_exit_0() -> None:
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200, json={"id": VIDEO_ID, "status": "pending"}
        )
    )

    result = runner.invoke(
        app, ["video", "status", VIDEO_ID], env=_env()
    )

    assert result.exit_code == 0
    assert "pending" in result.output.lower()


# ===========================================================================
# Done status — includes URL in text mode
# ===========================================================================


@respx.mock
def test_status_done_exit_0_url_in_output() -> None:
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": VIDEO_ID,
                "status": "done",
                "url": "https://cdn.example.com/vid.mp4",
            },
        )
    )

    result = runner.invoke(
        app, ["video", "status", VIDEO_ID, "--output", "text"], env=_env()
    )

    assert result.exit_code == 0
    assert "https://cdn.example.com/vid.mp4" in result.output


# ===========================================================================
# JSON output format
# ===========================================================================


@respx.mock
def test_status_output_json_valid() -> None:
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": VIDEO_ID,
                "status": "done",
                "url": "https://cdn.example.com/vid.mp4",
            },
        )
    )

    result = runner.invoke(
        app, ["video", "status", VIDEO_ID, "--output", "json"], env=_env()
    )

    assert result.exit_code == 0
    parsed = json.loads(result.output.strip())
    assert parsed["id"] == VIDEO_ID
    assert parsed["status"] == "done"
    assert parsed["url"] == "https://cdn.example.com/vid.mp4"


@respx.mock
def test_status_output_json_pending_url_is_none() -> None:
    """When status is pending there is no url — JSON output must still be valid."""
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200, json={"id": VIDEO_ID, "status": "pending"}
        )
    )

    result = runner.invoke(
        app, ["video", "status", VIDEO_ID, "--output", "json"], env=_env()
    )

    assert result.exit_code == 0
    parsed = json.loads(result.output.strip())
    assert parsed["status"] == "pending"
    # url key must exist (may be null/None)
    assert "url" in parsed


# ===========================================================================
# API error
# ===========================================================================


@respx.mock
def test_status_api_401_exit_2() -> None:
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    result = runner.invoke(
        app, ["video", "status", VIDEO_ID], env=_env()
    )

    assert result.exit_code == 2


@respx.mock
def test_status_server_error_exit_2() -> None:
    """500 retries exhausted — should still exit 2."""
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        result = runner.invoke(
            app, ["video", "status", VIDEO_ID], env=_env()
        )

    assert result.exit_code == 2


# ===========================================================================
# Text mode — done without URL (edge case: API omits url field)
# ===========================================================================


@respx.mock
def test_status_done_without_url_field_still_exits_0() -> None:
    """If the API returns done but omits url, CLI must not crash."""
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200, json={"id": VIDEO_ID, "status": "done"}
        )
    )

    result = runner.invoke(
        app, ["video", "status", VIDEO_ID, "--output", "text"], env=_env()
    )

    assert result.exit_code == 0
    assert "done" in result.output.lower()
