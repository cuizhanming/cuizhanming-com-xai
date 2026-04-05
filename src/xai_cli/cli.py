import asyncio
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

app.add_typer(video_app, name="video")
app.add_typer(config_app, name="config")

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
