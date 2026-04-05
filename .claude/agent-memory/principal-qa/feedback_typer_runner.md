---
name: Typer CliRunner constraints
description: mix_stderr is not a constructor arg on Typer's CliRunner; use plain CliRunner() and rely on result.output
type: feedback
---

`typer.testing.CliRunner.__init__()` does not accept `mix_stderr`. Discovered when tests failed at collection time with `TypeError: unexpected keyword argument 'mix_stderr'`.

**Why:** Typer wraps Click's CliRunner but does not expose all Click constructor params. The typer version in use (0.24.1) omits this param.

**How to apply:** Always instantiate as `runner = CliRunner()` with no arguments. stderr output from `typer.echo(..., err=True)` is included in `result.output` by default (mixed). Access via `result.output` not `result.stderr`. The `result.stderr` attribute exists on the Result object but is empty unless you explicitly separate streams, which requires Click's runner directly.

## CliRunner is not a TTY — always pass --output explicitly

`sys.stdout.isatty()` returns `False` inside CliRunner, so `_resolve_output(None)` always returns `"json"` instead of `"text"`. Any test that asserts on text-format output (e.g. `"Image URL:"`, `"Saved to"`) must pass `--output text` explicitly. Tests that assert on JSON output work with the default (no `--output` needed).

**Why:** Discovered when image CLI tests failed because the happy-path test expected `"Image URL:"` but got JSON output.

**How to apply:** When writing CLI tests that check human-readable output, always add `"--output", "text"` to the invoke args list.
