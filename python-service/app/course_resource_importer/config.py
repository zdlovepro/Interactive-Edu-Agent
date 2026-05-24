from __future__ import annotations

from urllib.parse import SplitResult, urlsplit

from .errors import UnsafeUrlError

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PRIMARY_DOMAIN = "chaoxing.com"
DEFAULT_COURSE_URL_BASE = "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu"
DEFAULT_COURSE_QUERY_SUFFIX = (
    ("pageHeader", "0"),
    ("v", "0"),
    ("hideHead", "0"),
)
DEFAULT_USER_AGENT = "Interactive-Edu-Agent Course Resource Importer/1.0"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RATE_LIMIT_PER_HOST = 1.0


def is_allowed_chaoxing_host(host: str | None) -> bool:
    if not host:
        return False

    normalized_host = host.lower().strip(".")
    return normalized_host == ALLOWED_PRIMARY_DOMAIN or normalized_host.endswith(f".{ALLOWED_PRIMARY_DOMAIN}")


def validate_chaoxing_url(url: str) -> SplitResult:
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError("Only http/https Chaoxing course URLs are allowed.")

    if not is_allowed_chaoxing_host(parsed.hostname):
        raise UnsafeUrlError("Only chaoxing.com course URLs are allowed.")

    return parsed
