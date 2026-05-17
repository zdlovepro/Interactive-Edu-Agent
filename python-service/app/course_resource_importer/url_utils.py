from __future__ import annotations

from html import unescape
from urllib.parse import urljoin, urlsplit, urlunsplit


def normalize_and_validate_resource_url(url: str, base_url: str | None = None) -> str | None:
    if not url:
        return None

    candidate = unescape(str(url)).strip()
    if not candidate or candidate.startswith("#"):
        return None

    lowered = candidate.lower()
    if lowered.startswith(("javascript:", "data:", "file:")):
        return None

    if base_url:
        candidate = urljoin(base_url, candidate)

    parsed = urlsplit(candidate)
    if not parsed.scheme and candidate.startswith("//") and base_url:
        candidate = urljoin(base_url, candidate)
        parsed = urlsplit(candidate)

    if parsed.scheme.lower() not in {"http", "https"}:
        return None

    sanitized = parsed._replace(fragment="")
    return urlunsplit(sanitized)
