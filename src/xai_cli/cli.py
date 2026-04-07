import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.progress import BarColumn, DownloadColumn, Progress, TransferSpeedColumn

from .api import XAIClient
from .config import load_api_key, load_config, save_config
from .exceptions import (
    ImageBatchError,
    ImageBatchTimeoutError,
    ImageEditError,
    ImageGenerationError,
    VideoGenerationError,
    VideoGenerationTimeoutError,
    XAIAuthError,
    XAIValidationError,
)
from .image_utils import prepare_image_input

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NO_COLOR = bool(os.environ.get("NO_COLOR"))


def _stderr_console() -> Console:
    return Console(stderr=True, no_color=_NO_COLOR)


def _stdout_console() -> Console:
    return Console(no_color=_NO_COLOR)


def _resolve_output(flag: Optional[str]) -> str:
    if flag is not None:
        return flag
    return "text" if sys.stdout.isatty() else "json"


def _redact_key(key: str) -> str:
    if len(key) <= 3:
        return "***"
    return f"sk-...{key[-3:]}"


# ---------------------------------------------------------------------------
# App skeleton
# ---------------------------------------------------------------------------

app = typer.Typer(no_args_is_help=True)
video_app = typer.Typer(no_args_is_help=True)
config_app = typer.Typer(no_args_is_help=True)
image_app = typer.Typer(no_args_is_help=True)
batch_app = typer.Typer(no_args_is_help=True)

app.add_typer(video_app, name="video")
app.add_typer(config_app, name="config")
app.add_typer(image_app, name="image")
image_app.add_typer(batch_app, name="batch")

# ---------------------------------------------------------------------------
# xai video generate
# ---------------------------------------------------------------------------


@video_app.command("generate")
def video_generate(
    prompt: str = typer.Argument(..., help="Text prompt for video generation"),
    image: Optional[str] = typer.Option(None, "--image", help="Image path or HTTPS URL"),
    model: str = typer.Option("grok-imagine-video", "--model", help="Model ID"),
    duration: Optional[float] = typer.Option(None, "--duration", help="Duration in seconds"),
    aspect_ratio: Optional[str] = typer.Option(None, "--aspect-ratio", help="Aspect ratio e.g. 16:9"),
    resolution: Optional[str] = typer.Option(None, "--resolution", help="Resolution e.g. 1080p"),
    timeout: float = typer.Option(600.0, "--timeout", help="Polling timeout in seconds"),
    output: Optional[str] = typer.Option(None, "--output", help="Output format: text or json"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="XAI_API_KEY", help="xAI API key"),
    # Phase 2 placeholder — --reference-images is mutually exclusive with --image
    reference_images: bool = typer.Option(False, "--reference-images", hidden=True),
) -> None:
    """Submit a video generation request, poll until done, and print the result."""
    # Mutual exclusion guard (Phase 2 placeholder)
    if image and reference_images:
        typer.echo("Error: --image and --reference-images are mutually exclusive", err=True)
        raise typer.Exit(1)

    resolved_key = load_api_key(api_key)
    out_format = _resolve_output(output)
    err_console = _stderr_console()

    # Pre-flight: validate image before any network call
    image_value: Optional[str] = None
    if image is not None:
        try:
            image_value = prepare_image_input(image)
        except (ValueError, FileNotFoundError, PermissionError) as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1)

    # Spinner — only when stderr is a TTY
    use_spinner = sys.stderr.isatty() and not _NO_COLOR
    spinner_status = err_console.status("Generating video...") if use_spinner else None

    request_id: str = ""
    result: dict = {}

    def on_status(status: str) -> None:
        if spinner_status is not None:
            spinner_status.update(f"Generating video... (status: {status})")

    async def _run() -> None:
        nonlocal request_id, result
        async with XAIClient(resolved_key) as client:
            request_id = await client.generate_video(
                prompt=prompt,
                model=model,
                image=image_value,
                duration=duration,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
            )
            result = await client.poll_video(
                request_id,
                timeout_seconds=timeout,
                on_status=on_status,
            )

    try:
        if spinner_status:
            with spinner_status:
                asyncio.run(_run())
        else:
            asyncio.run(_run())
    except XAIAuthError:
        typer.echo("Authentication failed — check XAI_API_KEY", err=True)
        raise typer.Exit(2)
    except XAIValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    except (VideoGenerationError, VideoGenerationTimeoutError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)

    url = result.get("url", "")
    if out_format == "json":
        typer.echo(json.dumps({"id": request_id, "status": "done", "url": url}))
    else:
        typer.echo(f"Video URL: {url}")


# ---------------------------------------------------------------------------
# xai video status
# ---------------------------------------------------------------------------


@video_app.command("status")
def video_status(
    request_id: str = typer.Argument(..., help="Generation request ID"),
    output: Optional[str] = typer.Option(None, "--output", help="Output format: text or json"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="XAI_API_KEY", help="xAI API key"),
) -> None:
    """Check the status of a video generation by ID."""
    resolved_key = load_api_key(api_key)
    out_format = _resolve_output(output)

    async def _run() -> dict:
        async with XAIClient(resolved_key) as client:
            return await client.get_video_status(request_id)

    try:
        data = asyncio.run(_run())
    except XAIAuthError:
        typer.echo("Authentication failed — check XAI_API_KEY", err=True)
        raise typer.Exit(2)
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)

    status = data.get("status", "unknown")
    url = data.get("url") or None

    if out_format == "json":
        typer.echo(json.dumps({"id": request_id, "status": status, "url": url}))
    else:
        typer.echo(f"Status: {status}")
        if status == "done" and url:
            typer.echo(f"URL:    {url}")


# ---------------------------------------------------------------------------
# xai video download
# ---------------------------------------------------------------------------


@video_app.command("download")
def video_download(
    request_id: str = typer.Argument(..., help="Generation request ID"),
    output: Optional[str] = typer.Option(None, "--output", help="Output file path"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="XAI_API_KEY", help="xAI API key"),
) -> None:
    """Download a completed video to a local file."""
    resolved_key = load_api_key(api_key)
    out_path = Path(output) if output else Path(f"{request_id}.mp4")

    async def _get_status() -> dict:
        async with XAIClient(resolved_key) as client:
            return await client.get_video_status(request_id)

    try:
        data = asyncio.run(_get_status())
    except XAIAuthError:
        typer.echo("Authentication failed — check XAI_API_KEY", err=True)
        raise typer.Exit(2)
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)

    status = data.get("status", "unknown")
    if status != "done":
        typer.echo(f"Generation not yet complete (status: {status})", err=True)
        raise typer.Exit(1)

    url = data.get("url", "")
    err_console = _stderr_console()

    try:
        with httpx.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0)) or None

            use_progress = sys.stderr.isatty() and not _NO_COLOR
            if use_progress:
                progress = Progress(
                    "[progress.description]{task.description}",
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    console=err_console,
                )
                task = progress.add_task(f"Downloading {out_path.name}", total=total)
                with progress:
                    with out_path.open("wb") as fh:
                        for chunk in response.iter_bytes(chunk_size=65536):
                            fh.write(chunk)
                            progress.update(task, advance=len(chunk))
            else:
                with out_path.open("wb") as fh:
                    for chunk in response.iter_bytes(chunk_size=65536):
                        fh.write(chunk)

    except httpx.HTTPError as exc:
        typer.echo(f"Network error: {exc}", err=True)
        raise typer.Exit(2)

    typer.echo(f"Saved to {out_path}")


# ---------------------------------------------------------------------------
# xai image generate
# ---------------------------------------------------------------------------


@image_app.command("generate")
def image_generate(
    prompt: str = typer.Argument(..., help="Text prompt for image generation"),
    n: int = typer.Option(1, "--n", min=1, max=10, help="Number of images to generate (1–10)"),
    aspect_ratio: Optional[str] = typer.Option(None, "--aspect-ratio", help="e.g. 16:9, 1:1, 9:16"),
    resolution: Optional[str] = typer.Option(None, "--resolution", help="1k or 2k"),
    output: Optional[str] = typer.Option(None, "--output", help="Output format: text or json"),
    save: Optional[str] = typer.Option(None, "--save", help="Save image(s) to this path (prefix when n>1)"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="XAI_API_KEY", help="xAI API key"),
) -> None:
    """Generate image(s) from a text prompt."""
    resolved_key = load_api_key(api_key)
    out_format = _resolve_output(output)
    err_console = _stderr_console()

    use_spinner = sys.stderr.isatty() and not _NO_COLOR
    spinner_status = err_console.status("Generating image...") if use_spinner else None

    images: list[dict] = []

    async def _run() -> None:
        nonlocal images
        async with XAIClient(resolved_key) as client:
            images = await client.generate_image(
                prompt=prompt,
                n=n,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
            )

    try:
        if spinner_status:
            with spinner_status:
                asyncio.run(_run())
        else:
            asyncio.run(_run())
    except XAIAuthError:
        typer.echo("Authentication failed — check XAI_API_KEY", err=True)
        raise typer.Exit(2)
    except XAIValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    except ImageGenerationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)

    if save is None:
        # Print URLs / base64 data without saving
        if out_format == "json":
            payload = []
            for i, img in enumerate(images):
                entry: dict = {"index": i}
                if "url" in img:
                    entry["url"] = img["url"]
                else:
                    entry["b64_json"] = img.get("b64_json", "")
                payload.append(entry)
            typer.echo(json.dumps({"images": payload}))
        else:
            for img in images:
                if "url" in img:
                    typer.echo(f"Image URL: {img['url']}")
                else:
                    typer.echo("[base64 data]")
    else:
        # Download and save each image
        save_path = Path(save)
        stem = save_path.stem
        suffix = save_path.suffix or ".png"
        saved_paths: list[str] = []

        use_status = sys.stderr.isatty() and not _NO_COLOR

        for i, img in enumerate(images):
            if n == 1:
                dest = save_path if save_path.suffix else Path(f"{stem}{suffix}")
            else:
                dest = Path(f"{stem}-{i + 1}{suffix}")

            if "url" in img:
                status_msg = f"Saving {dest.name}..."
                dl_status = err_console.status(status_msg) if use_status else None
                try:
                    if dl_status:
                        with dl_status:
                            response = httpx.get(img["url"], follow_redirects=True)
                            response.raise_for_status()
                            dest.write_bytes(response.content)
                    else:
                        response = httpx.get(img["url"], follow_redirects=True)
                        response.raise_for_status()
                        dest.write_bytes(response.content)
                except httpx.HTTPError as exc:
                    typer.echo(f"Network error downloading image {i + 1}: {exc}", err=True)
                    raise typer.Exit(2)
            else:
                b64_data = img.get("b64_json", "")
                dest.write_bytes(base64.b64decode(b64_data))

            saved_paths.append(str(dest))

        if out_format == "json":
            typer.echo(json.dumps({"saved": saved_paths}))
        else:
            for path in saved_paths:
                typer.echo(f"Saved to {path}")


# ---------------------------------------------------------------------------
# xai image edit
# ---------------------------------------------------------------------------


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _collect_image_paths(value: str) -> list[Path]:
    """Return a list of image Paths from a file path, HTTPS URL, or directory."""
    p = Path(value)
    if p.is_dir():
        paths = sorted(
            f for f in p.iterdir() if f.is_file() and f.suffix.lower() in _IMAGE_EXTENSIONS
        )
        if not paths:
            raise ValueError(f"No supported images found in {value} (accepted: jpg, jpeg, png, webp)")
        return paths
    return [p]


@image_app.command("edit")
def image_edit(
    prompt: str = typer.Argument(..., help="Editing instructions"),
    image: str = typer.Option(..., "--image", help="Image path, HTTPS URL, or folder of images"),
    aspect_ratio: Optional[str] = typer.Option(None, "--aspect-ratio", help="e.g. 16:9, 1:1"),
    output: Optional[str] = typer.Option(None, "--output", help="Output format: text or json"),
    save: Optional[str] = typer.Option(None, "--save", help="Save path or folder (for batch)"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="XAI_API_KEY"),
) -> None:
    """Edit an image using a text prompt (image-to-image). Pass a folder to batch-edit all images inside."""
    resolved_key = load_api_key(api_key)
    out_format = _resolve_output(output)
    err_console = _stderr_console()

    # Collect source paths (single file, URL, or folder)
    try:
        source_paths = _collect_image_paths(image)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    is_batch = len(source_paths) > 1 or (not image.startswith("https://") and Path(image).is_dir())

    # Pre-flight: resolve all inputs before any network call
    resolved: list[tuple[Path, str]] = []  # (original_path, resolved_data)
    for src in source_paths:
        try:
            resolved.append((src, prepare_image_input(str(src))))
        except (ValueError, FileNotFoundError, PermissionError) as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1)

    # Validate --save is a folder when batch
    save_dir: Path | None = None
    save_file: Path | None = None
    if save is not None:
        save_path = Path(save)
        if is_batch:
            save_dir = save_path
            save_dir.mkdir(parents=True, exist_ok=True)
        else:
            save_file = save_path if save_path.suffix else Path(f"{save_path.stem}.png")

    use_spinner = sys.stderr.isatty() and not _NO_COLOR and not is_batch

    # results: list of (original_stem, url)
    results: list[tuple[str, str]] = []

    async def _run() -> None:
        async with XAIClient(resolved_key) as client:
            async def _edit_one(stem: str, data: str) -> tuple[str, str]:
                items = await client.edit_image(
                    prompt=prompt,
                    image=data,
                    aspect_ratio=aspect_ratio,
                )
                return stem, items[0].get("url", "")

            tasks = [
                _edit_one(src.stem, data)
                for src, data in resolved
            ]
            gathered = await asyncio.gather(*tasks)
            results.extend(gathered)

    spinner_status = err_console.status(
        f"Editing {len(resolved)} image{'s' if len(resolved) > 1 else ''}..."
    ) if use_spinner or is_batch else None

    try:
        if spinner_status:
            with spinner_status:
                asyncio.run(_run())
        else:
            asyncio.run(_run())
    except XAIAuthError:
        typer.echo("Authentication failed — check XAI_API_KEY", err=True)
        raise typer.Exit(2)
    except XAIValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    except ImageEditError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)

    # Output / save
    if save_dir is not None:
        saved: list[str] = []
        for stem, url in results:
            dest = save_dir / f"edited_{stem}.png"
            try:
                response = httpx.get(url, follow_redirects=True)
                response.raise_for_status()
                dest.write_bytes(response.content)
                saved.append(str(dest))
            except httpx.HTTPError as exc:
                typer.echo(f"Network error downloading {stem}: {exc}", err=True)
                raise typer.Exit(2)
        if out_format == "json":
            typer.echo(json.dumps({"saved": saved}))
        else:
            for path in saved:
                typer.echo(f"Saved to {path}")
    elif save_file is not None:
        _, url = results[0]
        try:
            response = httpx.get(url, follow_redirects=True)
            response.raise_for_status()
            save_file.write_bytes(response.content)
        except httpx.HTTPError as exc:
            typer.echo(f"Network error downloading image: {exc}", err=True)
            raise typer.Exit(2)
        if out_format == "json":
            typer.echo(json.dumps({"saved": [str(save_file)]}))
        else:
            typer.echo(f"Saved to {save_file}")
    else:
        if out_format == "json":
            typer.echo(json.dumps({"images": [{"index": i, "url": url} for i, (_, url) in enumerate(results)]}))
        else:
            for _, url in results:
                typer.echo(f"Image URL: {url}")


# ---------------------------------------------------------------------------
# xai config set
# ---------------------------------------------------------------------------


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key (e.g. api_key, default_model, timeout)"),
    value: str = typer.Argument(..., help="Value to set"),
) -> None:
    """Set a configuration value in ~/.config/xai/config.toml."""
    cfg = load_config()

    # Coerce numeric keys
    if key == "timeout":
        try:
            cfg[key] = int(value)
        except ValueError:
            typer.echo("Error: timeout must be an integer", err=True)
            raise typer.Exit(1)
    else:
        cfg[key] = value

    save_config(cfg)
    typer.echo(f"Set {key} in ~/.config/xai/config.toml")


# ---------------------------------------------------------------------------
# xai config show
# ---------------------------------------------------------------------------


@config_app.command("show")
def config_show() -> None:
    """Print the current effective configuration (redacts api_key)."""
    cfg = load_config()
    env_key = os.environ.get("XAI_API_KEY", "")

    # Effective api_key: env var takes precedence over file
    effective_key = env_key or cfg.get("api_key", "")
    redacted = _redact_key(effective_key) if effective_key else "(not set)"

    stdout = _stdout_console()
    stdout.print(f"api_key        = {redacted}")
    stdout.print(f"default_model  = {cfg.get('default_model', '(not set)')}")
    stdout.print(f"timeout        = {cfg.get('timeout', 600)}")
    if env_key:
        stdout.print("[dim]api_key sourced from XAI_API_KEY environment variable[/dim]")


# ---------------------------------------------------------------------------
# xai image batch submit
# ---------------------------------------------------------------------------


@batch_app.command("submit")
def image_batch_submit(
    prompts: list[str] = typer.Argument(..., help="One or more text prompts"),
    aspect_ratio: Optional[str] = typer.Option(None, "--aspect-ratio", help="e.g. 16:9, 1:1"),
    resolution: Optional[str] = typer.Option(None, "--resolution", help="1k or 2k"),
    name: Optional[str] = typer.Option(None, "--name", help="Optional batch name"),
    wait: bool = typer.Option(False, "--wait", help="Poll until batch completes"),
    output: Optional[str] = typer.Option(None, "--output", help="Output format: text or json"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="XAI_API_KEY"),
) -> None:
    """Submit a batch of image generation requests."""
    resolved_key = load_api_key(api_key)
    out_format = _resolve_output(output)
    err_console = _stderr_console()

    batch_id: str = ""
    final: dict = {}

    use_spinner = sys.stderr.isatty() and not _NO_COLOR

    async def _run() -> None:
        nonlocal batch_id, final
        async with XAIClient(resolved_key) as client:
            batch_id = await client.create_image_batch(name)
            for i, prompt in enumerate(prompts):
                await client.add_image_batch_request(
                    batch_id,
                    batch_request_id=f"req-{i}",
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                )
            if wait:
                spinner_status = err_console.status("Waiting for batch...") if use_spinner else None

                def on_status(data: dict) -> None:
                    if spinner_status is not None:
                        spinner_status.update(
                            f"Waiting for batch... ({data['num_pending']} pending)"
                        )

                if spinner_status:
                    with spinner_status:
                        final = await client.poll_batch(batch_id, on_status=on_status)
                else:
                    final = await client.poll_batch(batch_id, on_status=on_status)

    try:
        asyncio.run(_run())
    except XAIAuthError:
        typer.echo("Authentication failed — check XAI_API_KEY", err=True)
        raise typer.Exit(2)
    except XAIValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    except (ImageBatchError, ImageBatchTimeoutError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)

    if not wait:
        if out_format == "json":
            typer.echo(json.dumps({"batch_id": batch_id, "num_requests": len(prompts)}))
        else:
            typer.echo(f"Batch ID: {batch_id}")
    else:
        if out_format == "json":
            typer.echo(
                json.dumps(
                    {
                        "batch_id": batch_id,
                        "status": "complete",
                        "num_success": final.get("num_success", 0),
                        "num_error": final.get("num_error", 0),
                    }
                )
            )
        else:
            typer.echo(
                f"Batch {batch_id} complete: "
                f"{final.get('num_success', 0)} succeeded, "
                f"{final.get('num_error', 0)} failed"
            )


# ---------------------------------------------------------------------------
# xai image batch status
# ---------------------------------------------------------------------------


@batch_app.command("status")
def image_batch_status(
    batch_id: str = typer.Argument(..., help="Batch ID"),
    output: Optional[str] = typer.Option(None, "--output", help="Output format: text or json"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="XAI_API_KEY"),
) -> None:
    """Check the status of an image batch."""
    resolved_key = load_api_key(api_key)
    out_format = _resolve_output(output)

    async def _run() -> dict:
        async with XAIClient(resolved_key) as client:
            return await client.get_batch_status(batch_id)

    try:
        data = asyncio.run(_run())
    except XAIAuthError:
        typer.echo("Authentication failed — check XAI_API_KEY", err=True)
        raise typer.Exit(2)
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)

    if out_format == "json":
        typer.echo(json.dumps(data))
    else:
        typer.echo(f"Batch ID:    {data.get('id', batch_id)}")
        typer.echo(f"Requests:    {data.get('num_requests', 0)}")
        typer.echo(f"Pending:     {data.get('num_pending', 0)}")
        typer.echo(f"Succeeded:   {data.get('num_success', 0)}")
        typer.echo(f"Failed:      {data.get('num_error', 0)}")
        typer.echo(f"Cancelled:   {data.get('num_cancelled', 0)}")


# ---------------------------------------------------------------------------
# xai image batch results
# ---------------------------------------------------------------------------


@batch_app.command("results")
def image_batch_results(
    batch_id: str = typer.Argument(..., help="Batch ID"),
    save_dir: Optional[str] = typer.Option(None, "--save-dir", help="Directory to save images"),
    output: Optional[str] = typer.Option(None, "--output", help="Output format: text or json"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="XAI_API_KEY"),
) -> None:
    """Fetch results from a completed image batch."""
    resolved_key = load_api_key(api_key)
    out_format = _resolve_output(output)
    err_console = _stderr_console()

    all_results: list[dict] = []

    async def _run() -> None:
        nonlocal all_results
        async with XAIClient(resolved_key) as client:
            after: Optional[str] = None
            while True:
                page = await client.get_batch_results(batch_id, after=after)
                all_results.extend(page.get("results", []))
                if not page.get("has_more", False):
                    break
                after = page.get("last_id")

    try:
        asyncio.run(_run())
    except XAIAuthError:
        typer.echo("Authentication failed — check XAI_API_KEY", err=True)
        raise typer.Exit(2)
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)

    succeeded = [r for r in all_results if r.get("status") == "succeeded"]

    if save_dir is None:
        if out_format == "json":
            payload = [
                {
                    "id": r["batch_request_id"],
                    "url": r["result"]["data"][0]["url"],
                }
                for r in succeeded
            ]
            typer.echo(json.dumps({"results": payload}))
        else:
            for r in succeeded:
                url = r["result"]["data"][0]["url"]
                typer.echo(f"{r['batch_request_id']}: {url}")
    else:
        dest_dir = Path(save_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        use_spinner = sys.stderr.isatty() and not _NO_COLOR
        saved_paths: list[str] = []

        for r in succeeded:
            req_id = r["batch_request_id"]
            url = r["result"]["data"][0]["url"]
            dest = dest_dir / f"{req_id}.png"

            dl_status = err_console.status(f"Downloading {req_id}.png...") if use_spinner else None
            try:
                if dl_status:
                    with dl_status:
                        response = httpx.get(url, follow_redirects=True)
                        response.raise_for_status()
                        dest.write_bytes(response.content)
                else:
                    response = httpx.get(url, follow_redirects=True)
                    response.raise_for_status()
                    dest.write_bytes(response.content)
            except httpx.HTTPError as exc:
                typer.echo(f"Network error downloading {req_id}: {exc}", err=True)
                raise typer.Exit(2)

            saved_paths.append(str(dest))
            if out_format != "json":
                typer.echo(f"Saved to {dest}")

        if out_format == "json":
            typer.echo(json.dumps({"saved": saved_paths}))
