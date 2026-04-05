"""
Unit tests for xai_cli.image_utils.prepare_image_input.

No network calls are made in this module — pure filesystem / encoding logic.
"""

import base64
import os
import stat
import sys
from pathlib import Path

import pytest

from xai_cli.image_utils import prepare_image_input


# ---------------------------------------------------------------------------
# HTTPS URL — passthrough
# ---------------------------------------------------------------------------


def test_https_url_returned_unchanged() -> None:
    url = "https://example.com/frame.png"
    assert prepare_image_input(url) == url


def test_https_url_with_path_and_query_returned_unchanged() -> None:
    url = "https://cdn.example.com/images/thumb.jpg?v=2"
    assert prepare_image_input(url) == url


# ---------------------------------------------------------------------------
# HTTP URL — must be rejected
# ---------------------------------------------------------------------------


def test_http_url_raises_value_error() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        prepare_image_input("http://example.com/frame.png")


def test_http_url_error_message_mentions_https() -> None:
    """The error message must guide the user toward HTTPS."""
    with pytest.raises(ValueError) as exc_info:
        prepare_image_input("http://insecure.example.com/img.jpg")
    assert "HTTPS" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Local PNG file
# ---------------------------------------------------------------------------


def test_local_png_returns_data_uri(tmp_path: Path) -> None:
    img = tmp_path / "frame.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)  # minimal PNG-like bytes

    result = prepare_image_input(str(img))

    assert result.startswith("data:image/png;base64,")
    encoded_part = result[len("data:image/png;base64,"):]
    decoded = base64.b64decode(encoded_part)
    assert decoded == img.read_bytes()


def test_local_png_uppercase_extension(tmp_path: Path) -> None:
    """Extension matching must be case-insensitive (.PNG should work)."""
    img = tmp_path / "frame.PNG"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    result = prepare_image_input(str(img))
    assert result.startswith("data:image/png;base64,")


# ---------------------------------------------------------------------------
# Local JPEG file
# ---------------------------------------------------------------------------


def test_local_jpg_returns_jpeg_mime(tmp_path: Path) -> None:
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 4)  # minimal JPEG-like header

    result = prepare_image_input(str(img))

    assert result.startswith("data:image/jpeg;base64,")
    encoded_part = result[len("data:image/jpeg;base64,"):]
    decoded = base64.b64decode(encoded_part)
    assert decoded == img.read_bytes()


def test_local_jpeg_extension_returns_jpeg_mime(tmp_path: Path) -> None:
    img = tmp_path / "photo.jpeg"
    img.write_bytes(b"\xff\xd8\xff")

    result = prepare_image_input(str(img))
    assert result.startswith("data:image/jpeg;base64,")


# ---------------------------------------------------------------------------
# Missing file
# ---------------------------------------------------------------------------


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.png"
    with pytest.raises(FileNotFoundError):
        prepare_image_input(str(missing))


# ---------------------------------------------------------------------------
# Unsupported extension
# ---------------------------------------------------------------------------


def test_gif_raises_value_error(tmp_path: Path) -> None:
    img = tmp_path / "anim.gif"
    img.write_bytes(b"GIF89a")

    with pytest.raises(ValueError, match="unsupported image type"):
        prepare_image_input(str(img))


def test_bmp_raises_value_error(tmp_path: Path) -> None:
    img = tmp_path / "bitmap.bmp"
    img.write_bytes(b"BM")

    with pytest.raises(ValueError, match="unsupported image type"):
        prepare_image_input(str(img))


def test_no_extension_raises_value_error(tmp_path: Path) -> None:
    img = tmp_path / "no_extension"
    img.write_bytes(b"\x00")

    with pytest.raises(ValueError, match="unsupported image type"):
        prepare_image_input(str(img))


# ---------------------------------------------------------------------------
# Unreadable file (permission denied)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    sys.platform == "win32" or os.getuid() == 0,
    reason="chmod permission tests require a non-root POSIX environment",
)
def test_unreadable_file_raises_permission_error(tmp_path: Path) -> None:
    img = tmp_path / "locked.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    img.chmod(0o000)

    try:
        with pytest.raises(PermissionError):
            prepare_image_input(str(img))
    finally:
        # Restore so tmp_path cleanup can delete the file
        img.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# webp — supported, should NOT raise
# ---------------------------------------------------------------------------


def test_webp_returns_webp_mime(tmp_path: Path) -> None:
    img = tmp_path / "image.webp"
    img.write_bytes(b"RIFF" + b"\x00" * 4 + b"WEBP")

    result = prepare_image_input(str(img))
    assert result.startswith("data:image/webp;base64,")
