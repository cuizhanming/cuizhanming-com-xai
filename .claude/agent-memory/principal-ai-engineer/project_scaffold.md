---
name: Project scaffold decisions
description: pyproject.toml choices, src layout, Python version floor, and build backend for the xai-cli package
type: project
---

- Package name: `xai-cli`, importable as `xai_cli`
- Layout: `src/xai_cli/` (src layout enforced by hatchling `packages = ["src/xai_cli"]`)
- Build backend: `hatchling` (not setuptools)
- Python floor: `>=3.10` — chosen to allow `tomllib` conditional (`tomli` backport for <3.11)
- Entry point: `xai = "xai_cli.cli:app"` — CLI engineer must create `src/xai_cli/cli.py` with a `app` Typer instance
- Core deps: `typer>=0.12.0`, `httpx>=0.27.0`, `rich>=13.0.0`, `tomli>=2.0.0; python_version < '3.11'`
- No CLI code lives in `api.py`, `image_utils.py`, or `exceptions.py` — strict separation enforced

**Why:** Clean src layout avoids import confusion when running tests from the project root. Hatchling is simpler than setuptools for pure-Python packages.

**How to apply:** When adding new modules, always place them under `src/xai_cli/`. CLI engineer owns `cli.py`; AI engineer owns `api.py`, `image_utils.py`, `exceptions.py`.
