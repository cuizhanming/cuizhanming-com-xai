---
name: xai-test-strategy
description: Testing strategy for this project — transport-layer mocking for httpx/requests, async polling state machine fixtures, Typer CliRunner patterns, and test category rules. Background knowledge for the QA agent; auto-loads when writing or reviewing tests.
user-invocable: false
---

# xAI CLI Test Strategy

## Test Categories

| Category | What it covers | Real HTTP? | Gate |
|---|---|---|---|
| Unit | API client, response parsers, exception mapping, retry logic | No — mock transport | Always run |
| CLI | Command invocation, argument parsing, exit codes, stdout/stderr | No — mock API client | Always run |
| Integration | Full round-trip against real xAI API | Yes | `XAI_INTEGRATION_TESTS=1` |

Run with: `uv run pytest` (unit + CLI), `XAI_INTEGRATION_TESTS=1 uv run pytest` (all).

## Mocking — Mock at the Transport Layer

**Never** mock at the method level (e.g. patching `client.get`). Mock at the HTTP transport so the full request-building and response-parsing code executes in tests.

### httpx — use `respx`

```python
import respx, httpx, pytest

@pytest.fixture
def mock_xai(respx_mock):
    return respx_mock

def test_submit_video(mock_xai):
    mock_xai.post("https://api.x.ai/v1/video/generations").mock(
        return_value=httpx.Response(200, json={"id": "vg-test", "status": "queued"})
    )
    # call the real client, not a mock
```

### requests — use `responses`

```python
import responses, pytest

@responses.activate
def test_submit_video():
    responses.add(responses.POST,
        "https://api.x.ai/v1/video/generations",
        json={"id": "vg-test", "status": "queued"}, status=200)
```

## Polling State Machine Fixtures

Always test every terminal and intermediate state:

```python
POLLING_SEQUENCES = {
    "immediate_success": [
        {"status": "queued"},
        {"status": "processing"},
        {"status": "succeeded", "video_url": "https://example.com/video.mp4"},
    ],
    "immediate_failure": [
        {"status": "queued"},
        {"status": "failed", "error": {"code": "content_policy", "message": "Rejected"}},
    ],
    "timeout": [
        {"status": "processing"},
        # ... repeat until timeout_seconds exceeded
    ],
}
```

See [references/polling-fixtures.md](references/polling-fixtures.md) for complete fixture implementations.

## CLI Testing — Typer CliRunner

```python
from typer.testing import CliRunner
from xai.cli import app

runner = CliRunner()

def test_video_generate_success(mock_xai):
    result = runner.invoke(app, ["video", "generate", "a cat on a skateboard"])
    assert result.exit_code == 0
    assert "https://example.com/video.mp4" in result.stdout

def test_video_generate_api_error(mock_xai):
    # mock a 401 response
    result = runner.invoke(app, ["video", "generate", "test"])
    assert result.exit_code == 2        # API error exit code
    assert "authentication" in result.output.lower()
```

## Output Format Tests

Always test both output modes:

```python
def test_json_output(mock_xai):
    result = runner.invoke(app, ["video", "generate", "test", "--output", "json"])
    data = json.loads(result.stdout)
    assert "video_url" in data

def test_text_output(mock_xai):
    result = runner.invoke(app, ["video", "generate", "test"])
    assert "https://" in result.stdout  # URL printed as plain text
```

## Required Test Coverage

Every PR must test:
- [ ] Happy path (submit → poll → succeed)
- [ ] `"failed"` status with error payload
- [ ] Polling timeout (`VideoGenerationTimeoutError`)
- [ ] 401 auth error
- [ ] 429 rate limit (verify retry behaviour)
- [ ] Exit code correctness for each error type
- [ ] `--output json` produces valid JSON
- [ ] `--output text` produces human-readable output
