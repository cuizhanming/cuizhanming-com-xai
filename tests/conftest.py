"""
Shared pytest fixtures for the xAI CLI test suite.

respx_mock is provided automatically by the respx library — no explicit
fixture definition needed here.  We only add project-level fixtures.
"""

import pytest


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Inject a fake API key via environment variable and return it."""
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    return "test-key"
