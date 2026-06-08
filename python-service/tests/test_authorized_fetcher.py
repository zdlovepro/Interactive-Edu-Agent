from __future__ import annotations

import asyncio

import pytest

from app.course_resource_importer import authorized_fetcher
from app.course_resource_importer.authorized_fetcher import (
    fetch_authorized_html,
    fetch_authorized_html_with_final_url,
    sanitize_headers_for_log,
)
from app.course_resource_importer.errors import DownstreamFetchError, RateLimitedError, UnauthorizedFetchError
from app.course_resource_importer.models import AuthorizedFetchContext


class _FakeResponse:
    def __init__(self, status: int, body: str = "<html></html>", url: str | None = None):
        self.status = status
        self._body = body
        self.url = url

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self, errors: str = "strict") -> str:
        return self._body


class _FakeClientSession:
    def __init__(
        self,
        response_status: int,
        response_body: str = "<html></html>",
        response_url: str | None = None,
        **kwargs,
    ):
        self._response = _FakeResponse(response_status, response_body, response_url)
        self.kwargs = kwargs
        self.calls: list[dict[str, object]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, headers=None, allow_redirects: bool = True):
        self.calls.append({"url": url, "headers": headers, "allow_redirects": allow_redirects})
        return self._response


def _build_context(**overrides) -> AuthorizedFetchContext:
    payload = {
        "cookie": "UID=abc123; _d=secret_cookie",
        "authorization": None,
        "referer": "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
        "rate_limit_per_host": 1000.0,
    }
    payload.update(overrides)
    return AuthorizedFetchContext(**payload)


def test_fetch_authorized_html_requires_explicit_credentials():
    with pytest.raises(UnauthorizedFetchError, match="Cookie or Authorization"):
        asyncio.run(
            fetch_authorized_html(
                "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
                AuthorizedFetchContext(rate_limit_per_host=1000.0),
            )
        )


def test_fetch_authorized_html_raises_unauthorized_on_403(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        authorized_fetcher.aiohttp,
        "ClientSession",
        lambda **kwargs: _FakeClientSession(403, "<html>forbidden</html>", **kwargs),
    )

    with pytest.raises(UnauthorizedFetchError, match="status 403"):
        asyncio.run(
            fetch_authorized_html(
                "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
                _build_context(),
            )
        )


def test_fetch_authorized_html_raises_rate_limited_on_429(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        authorized_fetcher.aiohttp,
        "ClientSession",
        lambda **kwargs: _FakeClientSession(429, "<html>slow down</html>", **kwargs),
    )

    with pytest.raises(RateLimitedError, match="rate limit"):
        asyncio.run(
            fetch_authorized_html(
                "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
                _build_context(),
            )
        )


def test_fetch_authorized_html_raises_downstream_error_on_500(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        authorized_fetcher.aiohttp,
        "ClientSession",
        lambda **kwargs: _FakeClientSession(500, "<html>error</html>", **kwargs),
    )

    with pytest.raises(DownstreamFetchError, match="status 500"):
        asyncio.run(
            fetch_authorized_html(
                "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
                _build_context(),
            )
        )


def test_fetch_authorized_html_with_final_url_returns_redirect_target(monkeypatch: pytest.MonkeyPatch):
    final_url = "https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId=123&cpi=final_cpi"
    monkeypatch.setattr(
        authorized_fetcher.aiohttp,
        "ClientSession",
        lambda **kwargs: _FakeClientSession(200, "<html>chapter</html>", response_url=final_url, **kwargs),
    )

    result = asyncio.run(
        fetch_authorized_html_with_final_url(
            "https://mooc1.chaoxing.com/mycourse/transfer?moocId=260728285",
            _build_context(),
        )
    )

    assert result.html == "<html>chapter</html>"
    assert result.final_url == final_url
    assert result.status == 200


def test_sanitize_headers_for_log_redacts_sensitive_values():
    headers = {
        "User-Agent": "Interactive-Edu-Agent Course Resource Importer/1.0",
        "Cookie": "UID=abc123; _d=secret_cookie",
        "Authorization": "Bearer super-secret-token",
        "Referer": "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
    }

    sanitized = sanitize_headers_for_log(headers)

    assert sanitized["User-Agent"] == headers["User-Agent"]
    assert sanitized["Referer"] == headers["Referer"]
    assert sanitized["Cookie"] == "<redacted>"
    assert sanitized["Authorization"] == "<redacted>"
    assert "secret_cookie" not in str(sanitized)
    assert "super-secret-token" not in str(sanitized)
