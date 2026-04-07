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

Pass `--api-key` to any command to override the configured key for that invocation.

---

## Image generation

### Generate an image

```bash
xai image generate "a red fox in a snowy forest"
```

```
Image URL: https://...
```

| Flag | Description |
|---|---|
| `--n 1–10` | Number of images to generate (default: 1) |
| `--aspect-ratio 16:9` | Aspect ratio (e.g. `16:9`, `1:1`, `9:16`) |
| `--resolution 1k\|2k` | Output resolution |
| `--save path.png` | Save image(s) locally (suffix becomes prefix when `--n > 1`) |
| `--output text\|json` | Output format (default: `text` on TTY, `json` otherwise) |
| `--api-key KEY` | Override `XAI_API_KEY` for this call |

```bash
# Generate 4 variations and save them
xai image generate "abstract watercolor" --n 4 --save output.png
# → output-1.png, output-2.png, output-3.png, output-4.png
```

### Edit an image (image-to-image)

```bash
xai image edit "make it look like a watercolor painting" --image photo.jpg
```

`--image` accepts a file path, an HTTPS URL, or a folder. Passing a folder edits every image inside it in one shot.

```bash
# Edit all images in a folder and save results
xai image edit "oil painting style" --image ~/photos --save ./edited
```

| Flag | Description |
|---|---|
| `--image PATH\|URL\|DIR` | Source image (required) |
| `--aspect-ratio 16:9` | Output aspect ratio |
| `--save PATH\|DIR` | Save path (file for single image, folder for directory input) |
| `--output text\|json` | Output format |
| `--api-key KEY` | Override `XAI_API_KEY` for this call |

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
# Wait for completion
xai image batch submit "a red apple" "a blue ocean" --wait
```

```bash
# Wait and download results in one shot
xai image batch submit "a red apple" "a blue ocean" --save-dir ./images
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

# Download all images
xai image batch results batch-xyz --save-dir ./images
```

### Batch image editing (folder → batch edit)

Apply a prompt to every image in a folder via the batch API:

```bash
# Submit edit requests for all images in a folder
xai image batch submit --image ~/photos "make it look like an oil painting"
```

```
Batch ID: batch-xyz
```

```bash
# Submit and download all edited images when done
xai image batch submit --image ~/photos "make it look like an oil painting" --save-dir ./edited
```

Supply one prompt per image to use different prompts for each:

```bash
xai image batch submit --image ~/photos "warm tones" "cool tones" "black and white"
```

#### `xai image batch submit` flags

| Flag | Description |
|---|---|
| `--image DIR` | Folder of images for image-to-image editing |
| `--aspect-ratio 16:9` | Output aspect ratio |
| `--resolution 1k\|2k` | Resolution (generation-only, ignored in edit mode) |
| `--name TEXT` | Optional batch name |
| `--wait` | Poll until batch completes before returning |
| `--save-dir DIR` | Download results to folder (implies `--wait`) |
| `--output text\|json` | Output format |
| `--api-key KEY` | Override `XAI_API_KEY` for this call |

---

## Video generation

### Generate a video

```bash
xai video generate "a red fox running through a snowy forest"
```

```
Video URL: https://...
```

| Flag | Description |
|---|---|
| `--image PATH\|URL` | Reference image (path or HTTPS URL) |
| `--model ID` | Model ID (default: `grok-imagine-video`) |
| `--duration SEC` | Duration in seconds |
| `--aspect-ratio 16:9` | Aspect ratio |
| `--resolution 1080p` | Resolution |
| `--timeout SEC` | Polling timeout in seconds (default: 600) |
| `--save PATH\|DIR` | Download video locally after generation |
| `--output text\|json` | Output format (default: `text` on TTY, `json` otherwise) |
| `--api-key KEY` | Override `XAI_API_KEY` for this call |

```bash
# Generate and save directly
xai video generate "timelapse of clouds" --save clouds.mp4

# Machine-readable output
xai video generate "timelapse of clouds over a mountain" --output json
```

```json
{"id": "req_abc123", "status": "done", "url": "https://..."}
```

When `--save` is used, the video is deleted from the server after a successful download.

### Check status

```bash
xai video status req_abc123
xai video status req_abc123 --output json
```

| Flag | Description |
|---|---|
| `--output text\|json` | Output format |
| `--api-key KEY` | Override `XAI_API_KEY` for this call |

### Download a completed video

```bash
xai video download req_abc123
xai video download req_abc123 --output fox-in-snow.mp4
```

| Flag | Description |
|---|---|
| `--output PATH` | Destination file path (default: `<request_id>.mp4`) |
| `--api-key KEY` | Override `XAI_API_KEY` for this call |

---

## Configuration

```bash
xai config set api_key your-key-here
xai config set timeout 300
xai config show
```

Config is stored at `~/.config/xai/config.toml`. The `XAI_API_KEY` environment variable takes precedence over the stored key.

---

## All commands

```bash
xai --help
xai image --help
xai image batch --help
xai video --help
```
