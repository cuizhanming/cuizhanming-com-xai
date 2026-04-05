import base64
from pathlib import Path

_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def prepare_image_input(value: str) -> str:
    if value.startswith("https://"):
        return value

    if value.startswith("http://"):
        raise ValueError("--image URL must use HTTPS")

    path = Path(value)
    ext = path.suffix.lower()
    if ext not in _MIME_MAP:
        raise ValueError(
            f'unsupported image type "{ext}". Accepted: .jpg, .jpeg, .png, .webp'
        )

    # Raises FileNotFoundError if missing, PermissionError if unreadable.
    raw = path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    mime = _MIME_MAP[ext]
    return f"data:{mime};base64,{encoded}"
