# PRD: Image-to-Video Generation (US-4)

**Status**: Approved
**Date**: 2026-04-05
**Phase**: 1 — CLI MVP

---

## Problem Statement

The xAI video API supports three generation modes. Phase 1 defined US-1 through US-3 for text-to-video only. Users who have a reference image (a product shot, a character, a scene) and want it animated have no CLI path today. Image-to-video is the highest-value incremental surface to unlock because it dramatically widens the creative use case without introducing a new top-level command or a new polling/download flow.

---

## 1. Command Shape

**Decision: `--image` is an optional flag on the existing `xai video generate` command.**

Rationale:
- The API models image-to-video as a variation of the same `POST /videos/generations` endpoint — same model, same polling, same download. A new sub-command implies a meaningfully different workflow; it does not exist here.
- Keeping one `generate` surface reduces the CLI surface area users must learn.
- The flag is mutually exclusive with `--reference-images` at the CLI layer (mirroring API semantics), enforced with a clear error message — no additional command disambiguation needed.
- Consistent with the CLI convention that flags modify behavior of a verb, not replace it.

---

## 2. Image Input Format

**`--image` accepts both a local file path and a public HTTPS URL.**

| Input type | Detected by | Wire format sent to API |
|---|---|---|
| Local file path | Value does not start with `https://` | Read file, base64-encode, send as `data:<mime>;base64,<data>` data URI |
| Public HTTPS URL | Value starts with `https://` | Pass through as-is |

Local file handling rules:
- Supported MIME types: `image/jpeg`, `image/png`, `image/webp`. Detect from file extension; reject others with a typed error before making any API call.
- No size pre-check beyond what the API enforces — let the API return a 4xx and surface it cleanly.
- No upload-to-storage step. Inline base64 is what the API accepts; do not invent an upload endpoint that does not exist.
- File is read once, base64-encoded in memory, discarded after the request is sent.

---

## 3. User Story US-4

**As a developer using the xAI CLI, I want to animate a source image into a video so that I can produce motion content from existing visual assets without switching to a separate tool.**

### Command syntax

```
xai video generate "<prompt>" --image <path-or-url>
```

### Acceptance criteria

1. **Flag accepted on generate**: `xai video generate "<prompt>" --image ./frame.jpg` submits a generation request and prints the job ID.
2. **Local JPEG/PNG/WebP**: When `--image` is a valid local file path, the CLI reads the file, encodes it as a base64 data URI, and includes it in the `image` field of the API request body.
3. **HTTPS URL passthrough**: When `--image` is an HTTPS URL, the CLI passes the URL string unchanged in the `image` field.
4. **Polling and download unchanged**: After submission, polling behavior and `xai video status` / `xai video download` commands are identical to text-to-video (US-1/US-2/US-3). No new post-submission flow.
5. **Prompt is still required**: Omitting the positional `<prompt>` argument when `--image` is present produces the same argument-missing error as plain `xai video generate`.
6. **Unsupported file type rejected locally**: Passing `--image ./file.gif` produces: `Error: unsupported image type ".gif". Accepted: .jpg, .jpeg, .png, .webp` — no API call is made.
7. **File not found rejected locally**: Passing `--image ./missing.jpg` produces: `Error: file not found: ./missing.jpg` — no API call is made.
8. **Mutual exclusion with --reference-images**: Using both `--image` and `--reference-images` in the same command produces: `Error: --image and --reference-images are mutually exclusive` — no API call is made.
9. **API error surfaces clearly**: If the API rejects the image (wrong dimensions, payload too large, etc.), the CLI prints the API error message verbatim and exits non-zero.
10. **Help text updated**: `xai video generate --help` documents the `--image` flag with a one-line description and an example.

---

## 4. Error Cases Specific to Image-to-Video

These are in addition to the error surface already defined for US-1 (prompt validation, auth failure, quota exhaustion, polling timeout, network errors).

| Error | Detection point | User-facing message |
|---|---|---|
| Unsupported file extension | CLI, pre-flight | `Error: unsupported image type "<ext>". Accepted: .jpg, .jpeg, .png, .webp` |
| File not found | CLI, pre-flight | `Error: file not found: <path>` |
| File unreadable (permissions) | CLI, pre-flight | `Error: cannot read file <path>: permission denied` |
| `--image` + `--reference-images` both set | CLI, pre-flight | `Error: --image and --reference-images are mutually exclusive` |
| API rejects image payload (4xx) | API response | Print API error message verbatim; exit 1 |
| HTTP URL (not HTTPS) passed | CLI, pre-flight | `Error: --image URL must use HTTPS` |

All pre-flight errors exit with code 1 before any network call is made.

---

## 5. Out of Scope (Defer Beyond Phase 1)

| Capability | Reason deferred |
|---|---|
| `--reference-images` (style guide mode) | Separate API semantic; separate user mental model. Own user story required. |
| Image dimension/size validation before upload | Requires knowing API limits per model; limits may change. Let API enforce. |
| Multiple `--image` flags / image arrays | API only accepts a single first-frame image; no need to design for it now. |
| Image format conversion (e.g., auto-convert GIF to PNG) | Adds FFmpeg/Pillow dependency; out of scope for a CLI MVP. |
| Stdin piping (`xai video generate "..." --image -`) | Useful but not in the core user journey. Deferred to Phase 2. |
| Presigned upload URL flow | API does not expose one today; do not anticipate. |

---

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Base64-encoded large images hit HTTP body size limits | Medium | Document a recommended max file size (~10 MB) in help text; surface API error clearly if exceeded |
| MIME type detection by extension is wrong for renamed files | Low | Acceptable for MVP; full magic-byte detection is Phase 2 |
| API changes `image` field name or format | Low | Isolated to one field in the API client module; easy to patch |

---

## Open Questions

None blocking implementation. The following are informational:

- Does xAI enforce a maximum image file size? If yes, the AI engineer should add a pre-flight size check with the documented limit. Check API docs at implementation time.
- Does the API accept `image/webp`? Assumed yes based on data URI support. Verify during integration testing.

---

## Success Metrics

| Metric | Target |
|---|---|
| All 10 acceptance criteria pass in CI | 100% before merge |
| `xai video generate "<prompt>" --image <local.jpg>` round-trip succeeds against live API | Manual smoke test in QA sign-off |
| Pre-flight errors exit before any network call | Verified via unit test with mocked HTTP client |
| `--help` output includes `--image` flag | Verified via CLI output snapshot test |
