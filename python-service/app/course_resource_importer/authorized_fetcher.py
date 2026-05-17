from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping

import aiohttp

from app.utils.logger import logger

from .config import validate_chaoxing_url
from .errors import DownstreamFetchError, RateLimitedError, UnauthorizedFetchError
from .models import AuthorizedFetchContext

_RATE_LIMIT_LOCKS: dict[str, asyncio.Lock] = {}
_RATE_LIMIT_NEXT_ALLOWED_AT: dict[str, float] = {}
_REDACTED = "<redacted>"


async def fetch_authorized_html(url: str, context: AuthorizedFetchContext) -> str:
    if not context.cookie and not context.authorization:
        raise UnauthorizedFetchError("Explicit Cookie or Authorization is required for authorized fetch.")

    parsed = validate_chaoxing_url(url)
    host = parsed.hostname or ""
    headers = _build_request_headers(context)

    await _apply_rate_limit(host, context.rate_limit_per_host)

    logger.info(
        "Fetching authorized HTML. url=%s host=%s timeout=%ss headers=%s",
        url,
        host,
        context.timeout_seconds,
        sanitize_headers_for_log(headers),
    )

    timeout = aiohttp.ClientTimeout(total=context.timeout_seconds)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
            async with session.get(url, headers=headers, allow_redirects=True) as response:
                body = await response.text(errors="replace")
                status = response.status

                if status in {401, 403}:
                    raise UnauthorizedFetchError(f"Upstream rejected the provided credentials with status {status}.")
                if status == 429:
                    raise RateLimitedError("Upstream rate limit encountered while fetching authorized HTML.")
                if 500 <= status <= 599:
                    raise DownstreamFetchError(f"Upstream returned status {status} while fetching authorized HTML.")
                if status >= 400:
                    raise DownstreamFetchError(f"Upstream returned unexpected status {status}.")

                logger.info("Authorized HTML fetched. url=%s host=%s status=%s bytes=%s", url, host, status, len(body))
                return body
    except asyncio.TimeoutError as exc:
        raise DownstreamFetchError("Timed out while fetching authorized HTML.") from exc
    except aiohttp.ClientError as exc:
        raise DownstreamFetchError(f"Failed to fetch authorized HTML: {exc}") from exc


def sanitize_headers_for_log(headers: Mapping[str, str]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for name, value in headers.items():
        if name.lower() in {"cookie", "authorization"} and value:
            sanitized[name] = _REDACTED
        else:
            sanitized[name] = value
    return sanitized


def _build_request_headers(context: AuthorizedFetchContext) -> dict[str, str]:
    headers = {"User-Agent": context.user_agent}
    if context.cookie:
        headers["Cookie"] = context.cookie
    if context.authorization:
        headers["Authorization"] = context.authorization
    if context.referer:
        headers["Referer"] = context.referer
    return headers


async def _apply_rate_limit(host: str, rate_limit_per_host: float) -> None:
    if not host or rate_limit_per_host <= 0:
        return

    interval_seconds = 1.0 / rate_limit_per_host
    host_lock = _RATE_LIMIT_LOCKS.get(host)
    if host_lock is None:
        host_lock = asyncio.Lock()
        _RATE_LIMIT_LOCKS[host] = host_lock

    async with host_lock:
        now = time.monotonic()
        next_allowed_at = _RATE_LIMIT_NEXT_ALLOWED_AT.get(host, now)
        delay = max(0.0, next_allowed_at - now)
        if delay > 0:
            await asyncio.sleep(delay)

        _RATE_LIMIT_NEXT_ALLOWED_AT[host] = max(next_allowed_at, time.monotonic()) + interval_seconds
