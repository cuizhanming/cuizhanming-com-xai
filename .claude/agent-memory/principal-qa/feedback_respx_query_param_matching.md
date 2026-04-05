---
name: respx query-param route matching order
description: When mocking URLs that share a base path but differ by query params, register the specific-param route first and use params= kwarg
type: feedback
---

When registering multiple respx routes for the same URL path — one with and one without query params — the more general (no-params) route matches ALL requests including those with query strings unless the specific route is registered first using `params=`.

**Why:** respx evaluates routes in registration order and the first match wins. A bare URL like `respx.get(URL)` will consume requests to `URL?after=cursor` before the cursor-specific route ever gets a chance to match.

**How to apply:** Always register the most-specific route first:

```python
# Correct — specific route registered first
respx.get(RESULTS_URL, params={"after": "cursor-abc"}).mock(return_value=page2_response)
respx.get(RESULTS_URL).mock(return_value=page1_response)

# Wrong — base route swallows both calls; test hangs waiting for second route
respx.get(RESULTS_URL).mock(return_value=page1_response)
respx.get(f"{RESULTS_URL}?after=cursor-abc").mock(return_value=page2_response)
```

Discovered while writing `test_batch_results_paginates` — the test hung indefinitely because the paginated second call was returning page1 again, creating an infinite loop in the CLI's `while True` pagination loop.
