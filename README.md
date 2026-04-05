# xai-cli

Command-line interface for xAI APIs — generate, check, and download AI videos from the terminal.

## Install

```bash
pip install xai-cli
```

## Auth

Set your API key before running any command:

```bash
export XAI_API_KEY=your-key-here
```

Or save it permanently:

```bash
xai config set api_key your-key-here
```

## Quick start

### Generate a video

```bash
xai video generate "a red fox running through a snowy forest"
```

```
Video URL: https://video.x.ai/v1/results/req_abc123/output.mp4
```

Add `--output json` for machine-readable output:

```bash
xai video generate "timelapse of clouds over a mountain" --output json
```

```json
{"id": "req_abc123", "status": "done", "url": "https://..."}
```

Optional flags: `--image path/or/url`, `--model`, `--duration`, `--aspect-ratio`, `--resolution`, `--timeout`.

### Check generation status

```bash
xai video status req_abc123
```

```
Status: processing
```

```bash
xai video status req_abc123   # once complete
```

```
Status: done
URL:    https://video.x.ai/v1/results/req_abc123/output.mp4
```

### Download a completed video

```bash
xai video download req_abc123
```

```
Saved to req_abc123.mp4
```

Use `--output` to set a custom filename:

```bash
xai video download req_abc123 --output fox-in-snow.mp4
```

## All commands

```bash
xai --help
```
