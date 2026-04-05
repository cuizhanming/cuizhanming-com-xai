# xai-cli

Command-line interface for xAI APIs — generate images, edit images, and create AI videos from the terminal.

## Install

```bash
pip install xai-cli
```

Or run without installing:

```bash
uv run xai --help
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

---

## Image generation

### Generate an image

```bash
xai image generate "a red fox in a snowy forest"
```

```
Image URL: https://...
```

Optional flags: `--n 1–10`, `--aspect-ratio 16:9`, `--resolution 1k|2k`, `--save path.png`, `--output text|json`.

```bash
# Generate 4 variations and save them
xai image generate "abstract watercolor" --n 4 --save output.png
# → output-1.png, output-2.png, output-3.png, output-4.png
```

### Edit an image (image-to-image)

```bash
xai image edit "make it look like a watercolor painting" --image photo.jpg
```

Pass up to 5 source images with repeated `--image` flags:

```bash
xai image edit "blend these together" --image img1.png --image img2.png
```

Optional flags: `--aspect-ratio`, `--save path.png`, `--output text|json`.

### Batch image generation

Submit multiple prompts as a single batch (async, reduced cost, no rate limit impact):

```bash
# Submit and get a batch ID immediately
xai image batch submit "a red apple" "a blue ocean" "a green forest"
```

```
Batch ID: batch-xyz
```

```bash
# Or wait for completion
xai image batch submit "a red apple" "a blue ocean" --wait
```

```bash
# Check status
xai image batch status batch-xyz
```

```
Batch ID:    batch-xyz
Requests:    2
Pending:     0
Succeeded:   2
Failed:      0
Cancelled:   0
```

```bash
# Fetch result URLs
xai image batch results batch-xyz

# Or download all images
xai image batch results batch-xyz --save-dir ./images
```

---

## Video generation

### Generate a video

```bash
xai video generate "a red fox running through a snowy forest"
```

```
Video URL: https://...
```

Optional flags: `--image path/or/url`, `--model`, `--duration`, `--aspect-ratio`, `--resolution`, `--timeout`.

Add `--output json` for machine-readable output:

```bash
xai video generate "timelapse of clouds over a mountain" --output json
```

```json
{"id": "req_abc123", "status": "done", "url": "https://..."}
```

### Check status

```bash
xai video status req_abc123
```

### Download a completed video

```bash
xai video download req_abc123
xai video download req_abc123 --output fox-in-snow.mp4
```

---

## Configuration

```bash
xai config set api_key your-key-here
xai config set timeout 300
xai config show
```

---

## All commands

```bash
xai --help
xai image --help
xai image batch --help
xai video --help
```
