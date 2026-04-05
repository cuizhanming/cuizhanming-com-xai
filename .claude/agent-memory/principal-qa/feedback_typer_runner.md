---
name: Typer CliRunner constraints
description: mix_stderr is not a constructor arg on Typer's CliRunner; use plain CliRunner() and rely on result.output
type: feedback
---

`typer.testing.CliRunner.__init__()` does not accept `mix_stderr`. Discovered when tests failed at collection time with `TypeError: unexpected keyword argument 'mix_stderr'`.

**Why:** Typer wraps Click's CliRunner but does not expose all Click constructor params. The typer version in use (0.24.1) omits this param.

**How to apply:** Always instantiate as `runner = CliRunner()` with no arguments. stderr output from `typer.echo(..., err=True)` is included in `result.output` by default (mixed). Access via `result.output` not `result.stderr`. The `result.stderr` attribute exists on the Result object but is empty unless you explicitly separate streams, which requires Click's runner directly.
