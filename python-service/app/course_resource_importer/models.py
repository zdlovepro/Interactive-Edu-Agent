from __future__ import annotations

from dataclasses import dataclass

from .config import DEFAULT_RATE_LIMIT_PER_HOST, DEFAULT_TIMEOUT_SECONDS, DEFAULT_USER_AGENT


@dataclass(slots=True)
class ChaoxingCourseRef:
    courseid: str
    clazzid: str | None = None
    cpi: str | None = None
    enc: str | None = None
    t: str | None = None
    raw_url: str | None = None
    referer: str | None = None


@dataclass(slots=True)
class AuthorizedFetchContext:
    cookie: str | None = None
    authorization: str | None = None
    referer: str | None = None
    user_agent: str = DEFAULT_USER_AGENT
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    rate_limit_per_host: float = DEFAULT_RATE_LIMIT_PER_HOST
