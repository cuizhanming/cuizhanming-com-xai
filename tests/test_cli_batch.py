"""
CLI tests for `xai image batch` commands.

All HTTP is intercepted via respx at the transport layer.
CliRunner is used so no real process is spawned.

httpx.get (used in cli.py for --save-dir downloads) is patched via unittest.mock
because it is a synchronous call that respx does not intercept.

Key exit codes:
  0 — success
  1 — pre-flight error or missing API key
  2 — API / batch error
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

BATCHES_URL = f"{_BASE_URL}/batches"
BATCH_ID = "batch-test-001"
STATUS_URL = f"{_BASE_URL}/batches/{BATCH_ID}"
REQUESTS_URL = f"{_BASE_URL}/batches/{BATCH_ID}/requests"
RESULTS_URL = f"{_BASE_URL}/batches/{BATCH_ID}/results"


def _env(extra: dict | None = None) -> dict:
    base = {"XAI_API_KEY": "test-key", "NO_COLOR": "1"}
    if extra:
        base.update(extra)
    return base


def _fake_httpx_get() -> MagicMock:
    """Return a mock that stands in for httpx.get() during --save-dir tests."""
    mock_response = MagicMock()
    mock_response.content = b"fake-image-bytes"
    mock_response.raise_for_status = MagicMock()
    mock_get = MagicMock(return_value=mock_response)
    return mock_get


def _batch_status_response(num_pending: int = 0, num_success: int = 1) -> dict:
    return {
        "id": BATCH_ID,
        "num_requests": num_success + num_pending,
        "num_pending": num_pending,
        "num_success": num_success,
        "num_error": 0,
        "num_cancelled": 0,
    }


def _results_page(
    req_ids: list[str],
    has_more: bool = False,
    last_id: str | None = None,
) -> dict:
    results = [
        {
            "batch_request_id": req_id,
            "status": "succeeded",
            "result": {"data": [{"url": f"https://img.example.com/{req_id}.png"}]},
        }
        for req_id in req_ids
    ]
    return {"results": results, "has_more": has_more, "last_id": last_id}


# ===========================================================================
# image batch submit
# ===========================================================================


@respx.mock
def test_batch_submit_happy_path_exit_0() -> None:
    """Two prompts submitted → exits 0 and prints the batch ID."""
    respx.post(BATCHES_URL).mock(
        return_value=httpx.Response(200, json={"id": BATCH_ID})
    )
    respx.post(REQUESTS_URL).mock(
        return_value=httpx.Response(200, json={})
    )

    result = runner.invoke(
        app,
        ["image", "batch", "submit", "prompt one", "prompt two", "--output", "text"],
        env=_env(),
    )

    assert result.exit_code == 0
    assert BATCH_ID in result.output


@respx.mock
def test_batch_submit_output_json() -> None:
    """--output json → valid JSON with batch_id and num_requests=2."""
    respx.post(BATCHES_URL).mock(
        return_value=httpx.Response(200, json={"id": BATCH_ID})
    )
    respx.post(REQUESTS_URL).mock(
        return_value=httpx.Response(200, json={})
    )

    result = runner.invoke(
        app,
        ["image", "batch", "submit", "prompt one", "prompt two", "--output", "json"],
        env=_env(),
    )

    assert result.exit_code == 0
    parsed = json.loads(result.output.strip())
    assert parsed["batch_id"] == BATCH_ID
    assert parsed["num_requests"] == 2


@respx.mock
def test_batch_submit_with_wait_exit_0() -> None:
    """--wait polls until num_pending==0 → exits 0 and prints 'complete'."""
    respx.post(BATCHES_URL).mock(
        return_value=httpx.Response(200, json={"id": BATCH_ID})
    )
    respx.post(REQUESTS_URL).mock(
        return_value=httpx.Response(200, json={})
    )
    respx.get(STATUS_URL).mock(
        side_effect=[
            httpx.Response(200, json=_batch_status_response(num_pending=1, num_success=0)),
            httpx.Response(200, json=_batch_status_response(num_pending=0, num_success=1)),
        ]
    )

    with patch("xai_cli.api.asyncio.sleep", new_callable=AsyncMock):
        result = runner.invoke(
            app,
            ["image", "batch", "submit", "a prompt", "--wait", "--output", "text"],
            env=_env(),
        )

    assert result.exit_code == 0
    assert "complete" in result.output.lower()


@respx.mock
def test_batch_submit_401_exit_2() -> None:
    """401 on batch creation → exits 2."""
    respx.post(BATCHES_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    result = runner.invoke(
        app,
        ["image", "batch", "submit", "a prompt", "--output", "text"],
        env=_env(),
    )

    assert result.exit_code == 2


def test_batch_submit_missing_api_key_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """No API key in env or config → exits 1."""
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with patch("xai_cli.config.load_config", return_value={}):
        result = runner.invoke(
            app,
            ["image", "batch", "submit", "a prompt"],
        )

    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "api key" in combined.lower() or "xai_api_key" in combined.lower()


# ===========================================================================
# image batch status
# ===========================================================================


@respx.mock
def test_batch_status_happy_path_text() -> None:
    """Text output must contain a 'Pending:' line."""
    respx.get(STATUS_URL).mock(
        return_value=httpx.Response(200, json=_batch_status_response(num_pending=3, num_success=2))
    )

    result = runner.invoke(
        app,
        ["image", "batch", "status", BATCH_ID, "--output", "text"],
        env=_env(),
    )

    assert result.exit_code == 0
    assert "Pending:" in result.output


@respx.mock
def test_batch_status_output_json() -> None:
    """--output json → valid JSON containing num_pending."""
    status_data = _batch_status_response(num_pending=2, num_success=3)
    respx.get(STATUS_URL).mock(
        return_value=httpx.Response(200, json=status_data)
    )

    result = runner.invoke(
        app,
        ["image", "batch", "status", BATCH_ID, "--output", "json"],
        env=_env(),
    )

    assert result.exit_code == 0
    parsed = json.loads(result.output.strip())
    assert "num_pending" in parsed
    assert parsed["num_pending"] == 2


@respx.mock
def test_batch_status_401_exit_2() -> None:
    """401 from status endpoint → exits 2."""
    respx.get(STATUS_URL).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    result = runner.invoke(
        app,
        ["image", "batch", "status", BATCH_ID, "--output", "text"],
        env=_env(),
    )

    assert result.exit_code == 2


# ===========================================================================
# image batch results
# ===========================================================================


@respx.mock
def test_batch_results_prints_urls() -> None:
    """One succeeded item → text output contains 'req-0: https://...'."""
    respx.get(RESULTS_URL).mock(
        return_value=httpx.Response(200, json=_results_page(["req-0"]))
    )

    result = runner.invoke(
        app,
        ["image", "batch", "results", BATCH_ID, "--output", "text"],
        env=_env(),
    )

    assert result.exit_code == 0
    assert "req-0" in result.output
    assert "https://img.example.com/req-0.png" in result.output


@respx.mock
def test_batch_results_output_json() -> None:
    """--output json → valid JSON with a 'results' list."""
    respx.get(RESULTS_URL).mock(
        return_value=httpx.Response(200, json=_results_page(["req-0", "req-1"]))
    )

    result = runner.invoke(
        app,
        ["image", "batch", "results", BATCH_ID, "--output", "json"],
        env=_env(),
    )

    assert result.exit_code == 0
    parsed = json.loads(result.output.strip())
    assert "results" in parsed
    assert len(parsed["results"]) == 2
    assert parsed["results"][0]["id"] == "req-0"
    assert parsed["results"][1]["id"] == "req-1"


@respx.mock
def test_batch_results_skips_failed_items() -> None:
    """Mix of succeeded + failed results → only succeeded items appear in output."""
    page = {
        "results": [
            {
                "batch_request_id": "req-0",
                "status": "succeeded",
                "result": {"data": [{"url": "https://img.example.com/req-0.png"}]},
            },
            {
                "batch_request_id": "req-1",
                "status": "failed",
                "result": {},
            },
        ],
        "has_more": False,
        "last_id": None,
    }
    respx.get(RESULTS_URL).mock(
        return_value=httpx.Response(200, json=page)
    )

    result = runner.invoke(
        app,
        ["image", "batch", "results", BATCH_ID, "--output", "text"],
        env=_env(),
    )

    assert result.exit_code == 0
    assert "req-0" in result.output
    assert "req-1" not in result.output


@respx.mock
def test_batch_results_save_dir_downloads_image(tmp_path: Path) -> None:
    """--save-dir → each succeeded image is downloaded and saved;
    output contains 'Saved to' with a path in the requested directory."""
    respx.get(RESULTS_URL).mock(
        return_value=httpx.Response(200, json=_results_page(["req-0"]))
    )

    with patch("xai_cli.cli.httpx.get", _fake_httpx_get()):
        result = runner.invoke(
            app,
            [
                "image", "batch", "results", BATCH_ID,
                "--save-dir", str(tmp_path),
                "--output", "text",
            ],
            env=_env(),
        )

    assert result.exit_code == 0
    assert "Saved to" in result.output
    saved_file = tmp_path / "req-0.png"
    assert saved_file.exists()
    assert saved_file.read_bytes() == b"fake-image-bytes"


@respx.mock
def test_batch_results_paginates() -> None:
    """has_more=True on first call → second call is made; both pages are collected."""
    page1 = _results_page(["req-0"], has_more=True, last_id="cursor-abc")
    page2 = _results_page(["req-1"], has_more=False, last_id=None)

    # Register the more-specific route (with ?after=) first so respx matches it
    # before falling through to the base URL route.
    respx.get(RESULTS_URL, params={"after": "cursor-abc"}).mock(
        return_value=httpx.Response(200, json=page2)
    )
    respx.get(RESULTS_URL).mock(
        return_value=httpx.Response(200, json=page1)
    )

    result = runner.invoke(
        app,
        ["image", "batch", "results", BATCH_ID, "--output", "json"],
        env=_env(),
    )

    assert result.exit_code == 0
    parsed = json.loads(result.output.strip())
    assert len(parsed["results"]) == 2
    ids = [r["id"] for r in parsed["results"]]
    assert "req-0" in ids
    assert "req-1" in ids
