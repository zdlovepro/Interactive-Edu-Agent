class CourseResourceImporterError(Exception):
    """Base exception for authorized course resource importing."""


class InvalidCourseRefError(CourseResourceImporterError):
    """Raised when the provided course reference is incomplete or malformed."""


class UnauthorizedFetchError(CourseResourceImporterError):
    """Raised when no explicit credentials are provided or upstream rejects them."""


class RateLimitedError(CourseResourceImporterError):
    """Raised when the upstream site returns a rate-limit response."""


class DownstreamFetchError(CourseResourceImporterError):
    """Raised when the upstream site is unavailable or the request fails."""


class UnsafeUrlError(CourseResourceImporterError):
    """Raised when a URL is outside the allowed host or scheme policy."""
