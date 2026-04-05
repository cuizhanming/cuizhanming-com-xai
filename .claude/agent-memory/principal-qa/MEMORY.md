# QA Memory Index

- [Typer CliRunner constraints](feedback_typer_runner.md) — mix_stderr not available on Typer's CliRunner; pass via **extra to invoke instead
- [xAI API shape and terminal states](project_xai_api_shape.md) — correct endpoint URLs, field names, and terminal states for the test suite
- [asyncio.sleep patch pattern](feedback_asyncio_sleep_patch.md) — patch target for instant polling tests
- [generate_video retry behavior](project_generate_video_no_retry.md) — POST uses no server retry; only GET paths use _get_with_server_retry
- [respx query-param route matching](feedback_respx_query_param_matching.md) — register params= route first or base URL swallows all calls; wrong order causes infinite pagination loop
