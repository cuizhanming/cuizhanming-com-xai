---
name: xai-product-context
description: xAI CLI product decisions — Phase 1 scope boundaries, accepted user stories, explicit out-of-scope items, and key tradeoff decisions already made. Background knowledge for the PM agent; auto-loads when scoping features or writing acceptance criteria.
user-invocable: false
---

# xAI CLI Product Context

## What This Product Is

A developer-facing CLI tool that wraps xAI APIs. The target user is a developer or power user comfortable with a terminal. This is not a GUI product.

## Phase 1 Scope — Video Generation

**In scope:**
- Submit a video generation request from a text prompt
- Poll and display live status while waiting
- Output the final video URL on success
- Show a clear error message (not a traceback) on failure
- Check the status of an existing generation by ID
- Download a completed video to a local file

**Explicitly out of scope for Phase 1:**
- Image generation
- Chat completions
- Embeddings
- Batch operations
- Streaming video progress
- Thumbnail extraction
- Video editing or post-processing
- Web UI or API server mode

Do not add Phase 2+ features to Phase 1, even if they seem small.

## Accepted Tradeoff Decisions

These are closed — do not re-litigate them:

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| HTTP library | `httpx` (async) | `requests` | Future-proofing for async CLI |
| CLI framework | `typer` | `click` directly | Less boilerplate, type-safe |
| Output on non-TTY | JSON | Plain text | Composability with pipes and scripts |
| Config file format | TOML | JSON, YAML | Human-friendly, Python standard (`tomllib`) |
| API key storage | Env var primary | Config file primary | Security — env vars don't persist to disk |
| Package name | TBD | — | To be decided before first PyPI publish |

## Core User Stories — Phase 1

### US-1: Generate a video
```
As a developer,
I want to run `xai video generate "a cat surfing"` and get a video URL,
so that I can integrate video generation into my scripts.

Acceptance criteria:
- Shows polling status while waiting
- Prints video URL when done
- Exits 0 on success, 2 on API error
- Works non-interactively (piped stdout gives JSON)
```

### US-2: Check generation status
```
As a developer,
I want to run `xai video status <id>` to check an in-progress generation,
so that I can script retries or status checks separately from generation.

Acceptance criteria:
- Prints current status and video_url if succeeded
- Exits 0 regardless of generation status (status check itself succeeded)
- Exits 2 on API error
```

### US-3: Download a video
```
As a developer,
I want to run `xai video download <id> [--output path]` to save a video locally,
so that I can use it in downstream workflows.

Acceptance criteria:
- Downloads to --output path if given, else current directory
- Fails clearly if generation has not succeeded yet
- Shows download progress
```

## Definition of Done

A feature is done when:
1. Happy path works as specified in the user story
2. All error paths produce clear messages (not tracebacks)
3. Exit codes are correct
4. `--output json` produces valid, parseable JSON
5. Tests cover all terminal states
6. `--help` is accurate and complete
