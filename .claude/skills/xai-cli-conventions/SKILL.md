---
name: xai-cli-conventions
description: This project's CLI architecture decisions — command hierarchy, exit codes, output format rules, TTY detection, config file schema, and argument conventions. Background knowledge for CLI and orchestrator agents; auto-loads when working on command modules.
user-invocable: false
---

# xAI CLI Conventions

## Command Hierarchy

```
xai
├── video
│   ├── generate   # Submit a prompt, poll until done, print result
│   ├── status     # Check status of an existing generation by ID
│   └── download   # Download video from a succeeded generation
└── config
    ├── set        # Set a config key (e.g. xai config set api-key <key>)
    └── show       # Print current config (redacts api-key)
```

Add new top-level groups only for distinct xAI API capability areas (image, chat, etc.) — not for utility concerns.

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | User or input error (bad argument, validation failure) |
| 2 | API or network error (request failed, polling timeout) |

Never exit with 0 when the operation failed. Never exit with non-zero for warnings.

## Output Format Rules

### TTY detection

```python
import sys
is_tty = sys.stdout.isatty()
```

- **TTY**: human-readable, coloured, with progress on stderr
- **Non-TTY (piped)**: machine-readable JSON by default, one value per line for bare outputs

### `--output` flag

Every command that produces data must support `--output [json|text]` (default: `text` when TTY, `json` when not TTY). Never add `--json` as a separate flag.

### Progress on stderr

Long-running commands show a spinner on **stderr** (not stdout) when stderr is a TTY. Use `rich.progress` or `typer`'s spinner. Stop the spinner before printing the final result.

### Respect `NO_COLOR`

Check `os.environ.get("NO_COLOR")` — if set (to any value), suppress all ANSI colour codes. Do not use `--no-color` as the primary mechanism; `NO_COLOR` is the standard.

## Configuration

### Precedence (highest to lowest)
1. CLI flag (`--api-key`)
2. Environment variable (`XAI_API_KEY`)
3. Config file (`~/.config/xai/config.toml`)

### Config file schema

```toml
# ~/.config/xai/config.toml
api_key = ""           # Never store here — use env var instead
default_model = ""     # Optional model override
timeout = 600          # Polling timeout in seconds
```

`api_key` in config is a convenience for development only. Document this clearly. In `xai config show`, always redact: show `api_key = "sk-...abc"`.

## Argument Conventions

- IDs (generation IDs) are positional arguments: `xai video status <id>`
- Options with values use `--name value` form, not `--name=value`
- Boolean flags: `--flag` to enable, `--no-flag` to disable (Typer default)
- File paths: always accept `-` as stdin/stdout where applicable

## Framework

Use **Typer** unless `pyproject.toml` already has Click as a dependency. Typer wraps Click and provides auto-generated `--help`, shell completion, and type safety.

Entry point in `pyproject.toml`:
```toml
[project.scripts]
xai = "xai.cli:app"
```
