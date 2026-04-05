---
name: US-4 image-to-video key design decisions
description: Rationale for command shape and image input handling decisions made for US-4
type: project
---

Key decisions locked for US-4 (image-to-video, 2026-04-05):

1. `--image` is a flag on `xai video generate`, NOT a new sub-command. Same endpoint, same polling, same download — no workflow divergence justifies a new command surface.

2. `--image` accepts both local file paths and HTTPS URLs. Local files are base64-encoded inline as data URIs. No upload-to-storage step because the API does not expose one.

3. Supported MIME types: jpeg, png, webp. Detected by file extension. GIF and other formats rejected pre-flight with a typed error.

4. `--image` and `--reference-images` are mutually exclusive at the CLI layer (mirrors API semantics). Both set simultaneously = pre-flight error, no API call.

5. Reference images mode (`--reference-images`) is explicitly out of scope for Phase 1. It has a different user mental model and needs its own user story.

**Why:** These decisions were made to minimize CLI surface area, match API semantics exactly, and avoid adding dependencies (no FFmpeg/Pillow for conversion, no upload service).

**How to apply:** Do not reopen command shape or image input format decisions without a clear user need that this rationale does not address.
