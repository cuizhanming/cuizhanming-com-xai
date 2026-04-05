import os
import sys
from pathlib import Path

import typer

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

_CONFIG_PATH = Path.home() / ".config" / "xai" / "config.toml"


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    try:
        with _CONFIG_PATH.open("rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}


def save_config(data: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, value in data.items():
        if isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        elif isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        else:
            lines.append(f"{key} = {value}")
    _CONFIG_PATH.write_text("\n".join(lines) + "\n")


def load_api_key(flag_value: str | None) -> str:
    if flag_value:
        return flag_value

    env_val = os.environ.get("XAI_API_KEY")
    if env_val:
        return env_val

    cfg = load_config()
    file_val = cfg.get("api_key", "")
    if file_val:
        return file_val

    typer.echo(
        "Error: API key not found. Set XAI_API_KEY, pass --api-key, "
        "or run `xai config set api_key <key>`.",
        err=True,
    )
    raise typer.Exit(1)
