import asyncio
from typing import Callable

import httpx

from .exceptions import (
    VideoGenerationError,
    VideoGenerationTimeoutError,
    XAIAuthError,
    XAIRateLimitError,
    XAIServerError,
    XAIValidationError,
)

_BASE_URL = "https://api.x.ai/v1"
_TERMINAL_STATES = {"done", "expired", "failed"}
_MAX_SERVER_RETRIES = 3


class XAIClient:
    def __init__(self, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "XAIClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code == 401:
            raise XAIAuthError(resp.text)
        if resp.status_code == 400:
            raise XAIValidationError(resp.text)
        if resp.status_code == 429:
            raise XAIRateLimitError(resp.text)
        if resp.status_code >= 500:
            raise XAIServerError(f"HTTP {resp.status_code}: {resp.text}")
        resp.raise_for_status()

    async def _request_with_server_retry(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(_MAX_SERVER_RETRIES):
            try:
                resp = await self._client.request(method, url, **kwargs)
                if resp.status_code < 500:
                    return resp
                last_exc = XAIServerError(f"HTTP {resp.status_code}: {resp.text}")
            except httpx.TransportError as exc:
                last_exc = exc
            if attempt < _MAX_SERVER_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]

    async def _get_with_server_retry(self, url: str) -> httpx.Response:
        return await self._request_with_server_retry("GET", url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_video(
        self,
        prompt: str,
        model: str = "grok-imagine-video",
        image: str | None = None,
        reference_images: list[str] | None = None,
        duration: float | None = None,
        aspect_ratio: str | None = None,
        resolution: str | None = None,
    ) -> str:
        body: dict = {"prompt": prompt, "model": model}
        if image is not None:
            body["image"] = image
        if reference_images is not None:
            body["reference_images"] = reference_images
        if duration is not None:
            body["duration"] = duration
        if aspect_ratio is not None:
            body["aspect_ratio"] = aspect_ratio
        if resolution is not None:
            body["resolution"] = resolution

        resp = await self._request_with_server_retry("POST", "/videos/generations", json=body)
        self._raise_for_status(resp)
        data = resp.json()
        return data["id"]

    async def get_video_status(self, request_id: str) -> dict:
        resp = await self._get_with_server_retry(f"/videos/{request_id}")
        self._raise_for_status(resp)
        return resp.json()

    async def poll_video(
        self,
        request_id: str,
        timeout_seconds: float = 600,
        on_status: Callable[[str], None] | None = None,
    ) -> dict:
        delay = 5.0
        elapsed = 0.0

        while elapsed < timeout_seconds:
            resp = await self._get_with_server_retry(f"/videos/{request_id}")

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", delay))
                await asyncio.sleep(retry_after)
                elapsed += retry_after
                continue

            self._raise_for_status(resp)
            data = resp.json()
            status: str = data["status"]

            if on_status is not None:
                on_status(status)

            if status == "done":
                return data

            if status in ("failed", "expired"):
                raise VideoGenerationError(
                    f"Video generation {status}: {data.get('error', {})}",
                    payload=data,
                )

            await asyncio.sleep(delay)
            elapsed += delay
            delay = min(delay * 1.5, 30.0)

        raise VideoGenerationTimeoutError(
            request_id=request_id,
            timeout_seconds=timeout_seconds,
        )
