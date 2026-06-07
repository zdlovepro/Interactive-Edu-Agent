from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from app.core.exceptions import (
    AppException,
    BUSINESS_VALIDATION_FAILED,
    DOWNSTREAM_SERVICE_ERROR,
    PARAM_ERROR,
    PythonServiceException,
)
from app.course_resource_importer import (
    AuthorizedFetchContext,
    ChaoxingCourseRef,
    DiscoveredResource,
    DownloadResult,
    DownstreamFetchError,
    InvalidCourseRefError,
    NoSlideImagesError,
    RateLimitedError,
    UnauthorizedFetchError,
    UnsafeUrlError,
    build_chaoxing_course_url,
    build_download_plan,
    build_pdf_from_slide_images,
    classify_resources,
    discover_resources_from_html,
    download_plan,
    fetch_authorized_html,
    parse_chaoxing_course_url,
    select_slide_images_from_results,
)
from app.course_resource_importer.config import DEFAULT_RATE_LIMIT_PER_HOST, DEFAULT_TIMEOUT_SECONDS, DEFAULT_USER_AGENT
from app.schemas.course_resource_import import (
    CourseResourceImportDiscoverRequest,
    CourseResourceImportDownloadRequest,
    CourseResourceImportHeaders,
    CourseResourceImportRequest,
    DiscoveredResourcePayload,
)
from app.utils.logger import logger

SOURCE_TYPE_CHAOXING_COURSE = "CHAOXING_COURSE"
DEFAULT_MIN_CONFIDENCE = 0.6
DEFAULT_DOWNLOAD_CONCURRENCY = 3


async def discover_course_resources(request: CourseResourceImportDiscoverRequest) -> dict[str, object]:
    raw_resources, classified_resources, course_ref, _page_url = await _discover_resource_batches(request)
    plan = build_download_plan(classified_resources, Path("."), min_confidence=DEFAULT_MIN_CONFIDENCE)

    logger.info(
        "Course-resource discovery finished. courseid=%s discovered=%s selected=%s ignored=%s",
        course_ref.courseid,
        len(classified_resources),
        plan.selected_count,
        plan.ignored_count,
    )
    return {
        "resources": [_serialize_resource(resource) for resource in classified_resources],
        "summary": {
            "discovered": len(classified_resources),
            "selected": plan.selected_count,
            "ignored": plan.ignored_count,
        },
    }


async def download_course_resources(request: CourseResourceImportDownloadRequest) -> dict[str, object]:
    headers = _resolve_headers(
        cookie=request.headers.cookie,
        authorization=request.headers.authorization,
        referer=request.headers.referer,
        user_agent=request.headers.user_agent,
    )
    resources = [item.to_resource() for item in request.resources]
    output_dir = request.output_path

    try:
        plan = build_download_plan(resources, output_dir, min_confidence=DEFAULT_MIN_CONFIDENCE)
        results = await download_plan(
            plan,
            cookie=headers.cookie,
            authorization=headers.authorization,
            referer=headers.referer,
            user_agent=headers.user_agent,
            concurrency=DEFAULT_DOWNLOAD_CONCURRENCY,
            rate_limit_per_host=DEFAULT_RATE_LIMIT_PER_HOST,
        )
        generated_pdf = _maybe_build_slide_pdf(
            build_pdf=request.build_pdf,
            results=results,
            output_pdf=output_dir / "courseware_from_images.pdf",
            title=_preferred_title(resources),
        )
        _write_json(
            output_dir / "resources.classified.json",
            {
                "source": "chaoxing_authorized_course_import",
                "resource_count": len(resources),
                "resources": [_serialize_resource(resource) for resource in resources],
            },
        )
        manifest_payload = _build_manifest(
            source="chaoxing_authorized_course_import",
            resources=resources,
            results=results,
            selected_count=plan.selected_count,
            ignored_count=plan.ignored_count,
            generated_pdf=generated_pdf,
        )
        parse_ready_payload = _build_parse_ready_manifest(
            source="chaoxing_authorized_course_import",
            resources=resources,
            results=results,
            generated_pdf=generated_pdf,
        )
        manifest_path = output_dir / "manifest.json"
        parse_ready_manifest_path = output_dir / "parse_ready_manifest.json"
        _write_json(manifest_path, manifest_payload)
        _write_json(parse_ready_manifest_path, parse_ready_payload)
    except Exception as exc:  # noqa: BLE001
        raise _translate_import_exception(exc) from exc

    downloaded_count = _count_results(results, {"success", "skipped"})
    failed_count = _count_results(results, {"failed"})
    ignored_count = _count_results(results, {"ignored"})
    logger.info(
        "Course-resource download finished. taskId=%s downloaded=%s failed=%s ignored=%s generatedPdf=%s",
        request.task_id,
        downloaded_count,
        failed_count,
        ignored_count,
        str(generated_pdf) if generated_pdf else "-",
    )
    return {
        "manifest_path": str(manifest_path),
        "parse_ready_manifest_path": str(parse_ready_manifest_path),
        "generated_pdf": str(generated_pdf) if generated_pdf else None,
        "summary": {
            "downloaded": downloaded_count,
            "failed": failed_count,
            "ignored": ignored_count,
        },
    }


async def import_course_resources(request: CourseResourceImportRequest) -> dict[str, object]:
    raw_resources, classified_resources, course_ref, page_url = await _discover_resource_batches(
        CourseResourceImportDiscoverRequest.model_validate(request.model_dump())
    )
    discover_payload = {
        "resources": [_serialize_resource(resource) for resource in classified_resources],
    }

    output_dir = request.output_path
    _write_json(
        output_dir / "resources.raw.json",
        {
            "source": "chaoxing_authorized_course_import",
            "courseid": course_ref.courseid,
            "clazzid": course_ref.clazzid,
            "page_url": page_url,
            "resource_count": len(raw_resources),
            "resources": [_serialize_resource(resource) for resource in raw_resources],
        },
    )
    _write_json(
        output_dir / "resources.classified.json",
        {
            "source": "chaoxing_authorized_course_import",
            "courseid": course_ref.courseid,
            "clazzid": course_ref.clazzid,
            "page_url": page_url,
            "resource_count": len(discover_payload["resources"]),
            "resources": discover_payload["resources"],
        },
    )

    download_request = CourseResourceImportDownloadRequest(
        task_id=request.output_path.name or "course_resource_import",
        resources=[DiscoveredResourcePayload.model_validate(item) for item in discover_payload["resources"]],
        headers=CourseResourceImportHeaders(
            cookie=request.cookie,
            authorization=request.authorization,
            referer=request.referer or page_url,
            user_agent=request.user_agent,
        ),
        output_dir=str(output_dir),
        build_pdf=request.build_pdf,
    )
    return await download_course_resources(download_request)


def _resolve_course_ref_and_url(
    request: CourseResourceImportDiscoverRequest | CourseResourceImportRequest,
) -> tuple[ChaoxingCourseRef, str]:
    _ensure_supported_source_type(request.source_type)

    if request.url:
        course_ref = _build_course_ref_from_url(request.url, request.referer)
        return course_ref, request.url

    if not request.courseid:
        raise AppException(PARAM_ERROR, "Either url or courseid must be provided.")

    course_ref = ChaoxingCourseRef(
        courseid=str(request.courseid).strip(),
        clazzid=_strip_optional(request.clazzid),
        cpi=_strip_optional(request.cpi),
        enc=_strip_optional(request.enc),
        t=_strip_optional(request.t),
        referer=_strip_optional(request.referer),
    )
    return course_ref, build_chaoxing_course_url(course_ref)


def _build_course_ref_from_url(url: str, referer: str | None) -> ChaoxingCourseRef:
    course_ref = ChaoxingCourseRef(**asdict(parse_chaoxing_course_url(url)))
    if referer:
        course_ref.referer = referer
    return course_ref


async def _discover_resource_batches(
    request: CourseResourceImportDiscoverRequest | CourseResourceImportRequest,
) -> tuple[list[DiscoveredResource], list[DiscoveredResource], ChaoxingCourseRef, str]:
    try:
        course_ref, page_url = _resolve_course_ref_and_url(request)
        headers = _resolve_headers(
            cookie=request.cookie,
            authorization=request.authorization,
            referer=request.referer or page_url,
            user_agent=request.user_agent,
        )
        html = await fetch_authorized_html(
            page_url,
            AuthorizedFetchContext(
                cookie=headers.cookie,
                authorization=headers.authorization,
                referer=headers.referer,
                user_agent=headers.user_agent or DEFAULT_USER_AGENT,
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
                rate_limit_per_host=DEFAULT_RATE_LIMIT_PER_HOST,
            ),
        )
        raw_resources = discover_resources_from_html(html, page_url=page_url, course_ref=course_ref)
        classified_resources = classify_resources(raw_resources)
        return raw_resources, classified_resources, course_ref, page_url
    except Exception as exc:  # noqa: BLE001
        raise _translate_import_exception(exc) from exc


def _resolve_headers(
    *,
    cookie: str | None,
    authorization: str | None,
    referer: str | None,
    user_agent: str | None = None,
) -> CourseResourceImportHeaders:
    if not cookie and not authorization:
        raise AppException(BUSINESS_VALIDATION_FAILED, "Explicit Cookie or Authorization is required.")
    return CourseResourceImportHeaders(cookie=cookie, authorization=authorization, referer=referer, user_agent=user_agent)


def _ensure_supported_source_type(source_type: str) -> None:
    if source_type.strip().upper() != SOURCE_TYPE_CHAOXING_COURSE:
        raise AppException(PARAM_ERROR, "Only CHAOXING_COURSE source_type is supported.")


def _maybe_build_slide_pdf(
    *,
    build_pdf: bool,
    results: list[DownloadResult],
    output_pdf: Path,
    title: str | None,
) -> Path | None:
    if not build_pdf:
        return None

    slide_images = select_slide_images_from_results(results)
    if not slide_images:
        return None

    try:
        return build_pdf_from_slide_images(slide_images, output_pdf, title=title)
    except NoSlideImagesError:
        return None


def _build_manifest(
    *,
    source: str,
    resources: list[DiscoveredResource],
    results: list[DownloadResult],
    selected_count: int,
    ignored_count: int,
    generated_pdf: Path | None,
) -> dict[str, object]:
    resource_map = {resource.resource_id: resource for resource in resources}
    files: list[dict[str, object]] = []
    for result in results:
        if result.status not in {"success", "skipped"} or not result.local_path:
            continue
        resource = resource_map.get(result.resource_id)
        files.append(
            {
                "resource_id": result.resource_id,
                "title": (resource.title if resource else None) or result.file_name,
                "type": _resource_type(result, resource),
                "file_name": result.file_name,
                "source_url": resource.url if resource else result.url,
                "local_path": result.local_path,
                "resource_kind": result.resource_kind,
                "mime_type": resource.mime_type if resource else None,
                "size": result.size_bytes,
                "md5": result.md5,
                "sha256": result.sha256,
                "confidence": resource.confidence if resource else None,
                "reason": resource.reason if resource else None,
            }
        )

    return {
        "source": source,
        "resource_count": len(resources),
        "selected_count": selected_count,
        "downloaded_count": _count_results(results, {"success", "skipped"}),
        "ignored_count": ignored_count,
        "files": files,
        "generated": {
            "pdf_from_slide_images": str(generated_pdf) if generated_pdf else None,
        },
    }


def _build_parse_ready_manifest(
    *,
    source: str,
    resources: list[DiscoveredResource],
    results: list[DownloadResult],
    generated_pdf: Path | None,
) -> dict[str, object]:
    resource_map = {resource.resource_id: resource for resource in resources}
    parse_ready_files: list[dict[str, object]] = []

    if generated_pdf is not None:
        parse_ready_files.append(
            {
                "type": "pdf",
                "path": str(generated_pdf),
                "title": "Courseware slide images merged PDF",
            }
        )

    for result in results:
        if result.status not in {"success", "skipped"} or not result.local_path:
            continue
        if result.resource_kind != "courseware_file":
            continue
        resource = resource_map.get(result.resource_id)
        parse_ready_files.append(
            {
                "type": "courseware_file",
                "path": result.local_path,
                "title": (resource.title if resource else None) or result.file_name,
            }
        )

    return {
        "source": source,
        "parse_ready_files": parse_ready_files,
    }


def _preferred_title(resources: list[DiscoveredResource]) -> str | None:
    for resource in resources:
        if resource.title:
            return resource.title
    return None


def _resource_type(result: DownloadResult, resource: DiscoveredResource | None) -> str:
    if resource and resource.extension:
        return resource.extension.lower().lstrip(".")
    suffix = Path(result.file_name).suffix.lower().lstrip(".")
    if suffix:
        return suffix
    return result.resource_kind


def _serialize_resource(resource: DiscoveredResource) -> dict[str, object]:
    return asdict(resource)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _count_results(results: list[DownloadResult], statuses: set[str]) -> int:
    return sum(1 for result in results if result.status in statuses)


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _translate_import_exception(exc: Exception) -> AppException:
    if isinstance(exc, AppException):
        return exc
    if isinstance(exc, (InvalidCourseRefError, UnsafeUrlError)):
        return AppException(PARAM_ERROR, str(exc))
    if isinstance(exc, UnauthorizedFetchError):
        return AppException(BUSINESS_VALIDATION_FAILED, str(exc))
    if isinstance(exc, (RateLimitedError, DownstreamFetchError)):
        return AppException(DOWNSTREAM_SERVICE_ERROR, str(exc))
    logger.exception("Unexpected course-resource import failure")
    return PythonServiceException("Course resource import failed")
