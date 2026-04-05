---
name: xai-api
description: xAI REST API reference for this project — video generation endpoints, async polling state machine, request/response schemas, auth, and error handling. Background knowledge for the AI engineer; auto-loads when working on API client code.
user-invocable: false
---

# xAI API Reference

Base URL: `https://api.x.ai/v1`
Auth: `Authorization: Bearer $XAI_API_KEY` on every request.

## Video Generation — Async Flow

Video generation is a two-step async operation. Never treat it as synchronous.

### Step 1 — Submit

```
POST /video/generations
Content-Type: application/json

{
  "model": "<model-id>",
  "prompt": "<text>",
  // optional: "n", "resolution", "duration_seconds"
}
```

Response (HTTP 200):
```json
{ "id": "vg-abc123", "status": "queued" }
```

Status on submission is always `"queued"` or `"processing"` — never `"succeeded"`.

### Step 2 — Poll

```
GET /video/generations/{id}
```

Response:
```json
{
  "id": "vg-abc123",
  "status": "queued" | "processing" | "succeeded" | "failed",
  "video_url": "https://...",   // only present when status == "succeeded"
  "error": { "code": "...", "message": "..." }  // only present when status == "failed"
}
```

**Terminal states**: `succeeded` and `failed`. All others require continued polling.
`video_url` is ONLY valid when `status == "succeeded"`. Never expose it otherwise.

### Recommended Polling Strategy

- Initial delay: 2 seconds
- Backoff: multiply by 1.5 each interval, cap at 30 seconds
- Default timeout: 10 minutes (configurable via `--timeout`)
- On timeout: raise `VideoGenerationTimeoutError`, not a generic exception

## Error Handling

| HTTP Status | Meaning | Action |
|---|---|---|
| 400 | Bad request (invalid params) | Raise `XAIValidationError` with message |
| 401 | Invalid or missing API key | Raise `XAIAuthError` |
| 429 | Rate limited | Retry with exponential backoff (respect `Retry-After` header) |
| 5xx | Server error | Retry up to 3 times, then raise `XAIServerError` |

All exceptions must carry: HTTP status code, xAI error code, human-readable message.

## Exception Hierarchy

```
XAIError (base)
├── XAIAuthError          # 401
├── XAIValidationError    # 400
├── XAIRateLimitError     # 429
├── XAIServerError        # 5xx
├── VideoGenerationError  # status == "failed" (includes xAI error payload)
└── VideoGenerationTimeoutError  # polling exceeded timeout
```

## HTTP Client

Use `httpx` (async preferred). Never `urllib`. Keep a single client instance per CLI invocation — do not create a new client per request.

## Detailed Reference

For full request/response schemas, model IDs, and resolution options, always fetch the live docs before implementing a new endpoint:
- `https://docs.x.ai/developers/model-capabilities/video/generation`

See [references/polling-patterns.md](references/polling-patterns.md) for proven polling implementation patterns.
