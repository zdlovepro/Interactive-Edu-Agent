from .authorized_fetcher import fetch_authorized_html, sanitize_headers_for_log
from .chaoxing_ref import build_chaoxing_course_url, parse_chaoxing_course_url
from .downloader import DownloadPlan, DownloadResult, build_download_plan, download_plan
from .html_resource_discoverer import discover_resources_from_html
from .js_resource_discoverer import discover_resources_from_js_text
from .json_resource_discoverer import discover_resources_from_json
from .resource_classifier import ImageProbe, classify_resource, classify_resources
from .errors import (
    CourseResourceImporterError,
    DownstreamFetchError,
    InvalidCourseRefError,
    RateLimitedError,
    UnauthorizedFetchError,
    UnsafeUrlError,
)
from .models import AuthorizedFetchContext, ChaoxingCourseRef
from .resource_models import DiscoveredResource

__all__ = [
    "AuthorizedFetchContext",
    "ChaoxingCourseRef",
    "CourseResourceImporterError",
    "DownloadPlan",
    "DownloadResult",
    "DownstreamFetchError",
    "DiscoveredResource",
    "ImageProbe",
    "InvalidCourseRefError",
    "RateLimitedError",
    "UnauthorizedFetchError",
    "UnsafeUrlError",
    "build_chaoxing_course_url",
    "build_download_plan",
    "classify_resource",
    "classify_resources",
    "discover_resources_from_html",
    "discover_resources_from_js_text",
    "discover_resources_from_json",
    "download_plan",
    "fetch_authorized_html",
    "parse_chaoxing_course_url",
    "sanitize_headers_for_log",
]
