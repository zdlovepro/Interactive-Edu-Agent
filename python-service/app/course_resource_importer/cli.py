from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from .authorized_fetcher import fetch_authorized_html
from .chaoxing_ref import build_chaoxing_course_url, parse_chaoxing_course_url
from .config import DEFAULT_USER_AGENT
from .downloader import DownloadPlan, DownloadResult, build_download_plan, download_plan
from .html_resource_discoverer import discover_resources_from_html
from .models import AuthorizedFetchContext, ChaoxingCourseRef
from .pdf_builder import build_pdf_from_slide_images, select_slide_images_from_results
from .resource_classifier import classify_resources
from .resource_models import DiscoveredResource


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "import-chaoxing-course":
            return _handle_import_command(args)
        if args.command == "discover":
            return _handle_discover_command(args)
        if args.command == "download":
            return _handle_download_command(args)
        if args.command == "build-pdf" or (args.command is None and _parse_bool(args.build_pdf)):
            return _handle_build_pdf_command(args)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.course_resource_importer.cli")
    parser.add_argument("--build-pdf", default="false")
    parser.add_argument("--manifest")
    parser.add_argument("--output")
    parser.add_argument("--title")

    subparsers = parser.add_subparsers(dest="command")

    import_parser = subparsers.add_parser("import-chaoxing-course")
    _add_course_ref_arguments(import_parser)
    _add_auth_arguments(import_parser)
    import_parser.add_argument("--output-dir", default=os.getenv("RESOURCE_OUTPUT_DIR"))
    import_parser.add_argument("--build-pdf", action="store_true", dest="build_pdf")
    import_parser.add_argument("--include-unknown", action="store_true")
    import_parser.add_argument("--min-confidence", type=float, default=0.6)
    import_parser.add_argument("--concurrency", type=int, default=3)
    import_parser.add_argument("--rate-limit-per-host", type=float, default=1.0)
    import_parser.add_argument("--user-agent", default=os.getenv("RESOURCE_USER_AGENT"))

    discover_parser = subparsers.add_parser("discover")
    _add_course_ref_arguments(discover_parser)
    _add_auth_arguments(discover_parser)
    discover_parser.add_argument("--output", required=True)
    discover_parser.add_argument("--user-agent", default=os.getenv("RESOURCE_USER_AGENT"))
    discover_parser.add_argument("--rate-limit-per-host", type=float, default=1.0)

    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("--resources", required=True)
    _add_auth_arguments(download_parser)
    download_parser.add_argument("--output-dir", default=os.getenv("RESOURCE_OUTPUT_DIR"), required=False)
    download_parser.add_argument("--include-unknown", action="store_true")
    download_parser.add_argument("--min-confidence", type=float, default=0.6)
    download_parser.add_argument("--concurrency", type=int, default=3)
    download_parser.add_argument("--rate-limit-per-host", type=float, default=1.0)
    download_parser.add_argument("--build-pdf", action="store_true", dest="build_pdf")

    pdf_parser = subparsers.add_parser("build-pdf")
    pdf_parser.add_argument("--manifest", required=True)
    pdf_parser.add_argument("--output", required=True)
    pdf_parser.add_argument("--title")

    return parser


def _add_course_ref_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--url")
    parser.add_argument("--courseid")
    parser.add_argument("--clazzid")
    parser.add_argument("--cpi")
    parser.add_argument("--enc")


def _add_auth_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cookie", default=os.getenv("RESOURCE_COOKIE"))
    parser.add_argument("--authorization", default=os.getenv("RESOURCE_AUTHORIZATION"))
    parser.add_argument("--referer", default=os.getenv("RESOURCE_REFERER"))


def _handle_import_command(args: argparse.Namespace) -> int:
    output_dir = _require_output_dir(args.output_dir)
    course_ref, page_url = _resolve_course_ref_and_url(args)

    raw_resources, classified_resources = asyncio.run(
        _discover_classified_resources(
            page_url=page_url,
            course_ref=course_ref,
            cookie=args.cookie,
            authorization=args.authorization,
            referer=args.referer or course_ref.referer or page_url,
            user_agent=args.user_agent,
            rate_limit_per_host=args.rate_limit_per_host,
        )
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_resource_payload(
        output_dir / "resources.raw.json",
        source="chaoxing_authorized_course_import",
        page_url=page_url,
        course_ref=course_ref,
        resources=raw_resources,
    )
    _write_resource_payload(
        output_dir / "resources.classified.json",
        source="chaoxing_authorized_course_import",
        page_url=page_url,
        course_ref=course_ref,
        resources=classified_resources,
    )

    plan = build_download_plan(
        classified_resources,
        output_dir,
        min_confidence=args.min_confidence,
        include_unknown=args.include_unknown,
    )
    results = asyncio.run(
        download_plan(
            plan,
            cookie=args.cookie,
            authorization=args.authorization,
            referer=args.referer or course_ref.referer or page_url,
            concurrency=args.concurrency,
            rate_limit_per_host=args.rate_limit_per_host,
        )
    )

    generated_pdf = _maybe_build_slide_pdf(
        build_pdf=bool(args.build_pdf),
        results=results,
        output_pdf=output_dir / "courseware_from_images.pdf",
        title=_preferred_course_title(classified_resources, course_ref),
    )

    manifest_payload = _build_custom_manifest(
        source="chaoxing_authorized_course_import",
        course_ref=course_ref,
        resources=classified_resources,
        results=results,
        plan=plan,
        generated_pdf=generated_pdf,
    )
    parse_ready_payload = _build_parse_ready_manifest(
        source="chaoxing_authorized_course_import",
        resources=classified_resources,
        results=results,
        generated_pdf=generated_pdf,
    )
    _write_json(output_dir / "manifest.json", manifest_payload)
    _write_json(output_dir / "parse_ready_manifest.json", parse_ready_payload)

    _print_stats(
        discovered=len(classified_resources),
        selected=plan.selected_count,
        downloaded=_downloaded_count(results),
        ignored=_ignored_count(results),
        generated_pdf=generated_pdf,
    )
    return 0


def _handle_discover_command(args: argparse.Namespace) -> int:
    output_path = Path(args.output).resolve()
    course_ref, page_url = _resolve_course_ref_and_url(args)

    raw_resources, classified_resources = asyncio.run(
        _discover_classified_resources(
            page_url=page_url,
            course_ref=course_ref,
            cookie=args.cookie,
            authorization=args.authorization,
            referer=args.referer or course_ref.referer or page_url,
            user_agent=args.user_agent,
            rate_limit_per_host=args.rate_limit_per_host,
        )
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_resource_payload(
        output_path,
        source="chaoxing_authorized_course_discovery",
        page_url=page_url,
        course_ref=course_ref,
        resources=classified_resources,
        raw_resources=raw_resources,
    )
    _print_stats(
        discovered=len(classified_resources),
        selected=0,
        downloaded=0,
        ignored=0,
        generated_pdf=None,
    )
    return 0


def _handle_download_command(args: argparse.Namespace) -> int:
    output_dir = _require_output_dir(args.output_dir)
    resources_payload = _load_resources_payload(Path(args.resources))
    course_ref = ChaoxingCourseRef(
        courseid=resources_payload.get("courseid") or "",
        clazzid=resources_payload.get("clazzid"),
    )
    resources = resources_payload["resources"]

    plan = build_download_plan(
        resources,
        output_dir,
        min_confidence=args.min_confidence,
        include_unknown=args.include_unknown,
    )
    results = asyncio.run(
        download_plan(
            plan,
            cookie=args.cookie,
            authorization=args.authorization,
            referer=args.referer or resources_payload.get("page_url"),
            concurrency=args.concurrency,
            rate_limit_per_host=args.rate_limit_per_host,
        )
    )

    generated_pdf = _maybe_build_slide_pdf(
        build_pdf=bool(args.build_pdf),
        results=results,
        output_pdf=output_dir / "courseware_from_images.pdf",
        title=_preferred_course_title(resources, course_ref),
    )

    manifest_payload = _build_custom_manifest(
        source=resources_payload.get("source", "chaoxing_authorized_course_import"),
        course_ref=course_ref,
        resources=resources,
        results=results,
        plan=plan,
        generated_pdf=generated_pdf,
    )
    parse_ready_payload = _build_parse_ready_manifest(
        source=resources_payload.get("source", "chaoxing_authorized_course_import"),
        resources=resources,
        results=results,
        generated_pdf=generated_pdf,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "manifest.json", manifest_payload)
    _write_json(output_dir / "parse_ready_manifest.json", parse_ready_payload)

    _print_stats(
        discovered=len(resources),
        selected=plan.selected_count,
        downloaded=_downloaded_count(results),
        ignored=_ignored_count(results),
        generated_pdf=generated_pdf,
    )
    return 0


def _handle_build_pdf_command(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    output_path = Path(args.output)
    results = _load_results_from_manifest(manifest_path)
    slide_images = select_slide_images_from_results(results)
    built_pdf = build_pdf_from_slide_images(slide_images, output_path, title=args.title)
    print(str(built_pdf))
    return 0


async def _discover_classified_resources(
    *,
    page_url: str,
    course_ref: ChaoxingCourseRef,
    cookie: str | None,
    authorization: str | None,
    referer: str | None,
    user_agent: str | None,
    rate_limit_per_host: float,
) -> tuple[list[DiscoveredResource], list[DiscoveredResource]]:
    html = await fetch_authorized_html(
        page_url,
        AuthorizedFetchContext(
            cookie=cookie,
            authorization=authorization,
            referer=referer,
            user_agent=user_agent or DEFAULT_USER_AGENT,
            rate_limit_per_host=rate_limit_per_host,
        ),
    )
    raw_resources = discover_resources_from_html(html, page_url=page_url, course_ref=course_ref)
    classified_resources = classify_resources(raw_resources)
    return raw_resources, classified_resources


def _resolve_course_ref_and_url(args: argparse.Namespace) -> tuple[ChaoxingCourseRef, str]:
    if args.url:
        course_ref = parse_chaoxing_course_url(args.url)
        return course_ref, args.url

    if not args.courseid:
        raise ValueError("Either --url or --courseid must be provided.")

    course_ref = ChaoxingCourseRef(
        courseid=str(args.courseid),
        clazzid=str(args.clazzid) if args.clazzid is not None else None,
        cpi=str(args.cpi) if args.cpi is not None else None,
        enc=str(args.enc) if args.enc is not None else None,
        referer=args.referer or os.getenv("RESOURCE_REFERER"),
    )
    return course_ref, build_chaoxing_course_url(course_ref)


def _require_output_dir(output_dir: str | None) -> Path:
    if not output_dir:
        raise ValueError("An output directory is required. Pass --output-dir or set RESOURCE_OUTPUT_DIR.")
    return Path(output_dir).resolve()


def _write_resource_payload(
    path: Path,
    *,
    source: str,
    page_url: str,
    course_ref: ChaoxingCourseRef,
    resources: list[DiscoveredResource],
    raw_resources: list[DiscoveredResource] | None = None,
) -> None:
    payload = {
        "source": source,
        "courseid": course_ref.courseid,
        "clazzid": course_ref.clazzid,
        "page_url": page_url,
        "resource_count": len(resources),
        "resources": [_serialize_resource(resource) for resource in resources],
    }
    if raw_resources is not None:
        payload["raw_resource_count"] = len(raw_resources)
        payload["raw_resources"] = [_serialize_resource(resource) for resource in raw_resources]
    _write_json(path, payload)


def _build_custom_manifest(
    *,
    source: str,
    course_ref: ChaoxingCourseRef,
    resources: list[DiscoveredResource],
    results: list[DownloadResult],
    plan: DownloadPlan,
    generated_pdf: Path | None,
) -> dict:
    resource_map = {resource.resource_id: resource for resource in resources}
    file_entries: list[dict] = []
    for result in results:
        if result.status not in {"success", "skipped"} or not result.local_path:
            continue
        resource = resource_map.get(result.resource_id)
        file_entries.append(
            {
                "title": (resource.title if resource else None) or result.file_name,
                "file_name": result.file_name,
                "local_path": result.local_path,
                "resource_kind": result.resource_kind,
                "mime_type": resource.mime_type if resource else None,
                "md5": result.md5,
                "sha256": result.sha256,
                "confidence": resource.confidence if resource else None,
                "reason": resource.reason if resource else None,
            }
        )

    return {
        "source": source,
        "courseid": course_ref.courseid or None,
        "clazzid": course_ref.clazzid,
        "resource_count": len(resources),
        "selected_count": plan.selected_count,
        "downloaded_count": _downloaded_count(results),
        "ignored_count": _ignored_count(results),
        "files": file_entries,
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
) -> dict:
    resource_map = {resource.resource_id: resource for resource in resources}
    parse_ready_files: list[dict] = []

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

    return build_pdf_from_slide_images(slide_images, output_pdf, title=title)


def _preferred_course_title(resources: list[DiscoveredResource], course_ref: ChaoxingCourseRef) -> str | None:
    for resource in resources:
        if resource.title:
            return resource.title
    return course_ref.courseid or None


def _load_resources_payload(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        resources = [_deserialize_resource(item) for item in payload]
        return {"resources": resources, "source": "chaoxing_authorized_course_discovery"}

    items = payload.get("resources", [])
    return {
        "source": payload.get("source"),
        "courseid": payload.get("courseid"),
        "clazzid": payload.get("clazzid"),
        "page_url": payload.get("page_url"),
        "resources": [_deserialize_resource(item) for item in items],
    }


def _load_results_from_manifest(manifest_path: Path) -> list[DownloadResult]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "results" in payload:
        return [DownloadResult(**item) for item in payload.get("results", [])]

    if "files" in payload:
        return [
            DownloadResult(
                resource_id=item.get("file_name") or item.get("local_path") or f"result_{index}",
                url=item.get("url", ""),
                status="success",
                local_path=item.get("local_path"),
                file_name=item.get("file_name") or Path(item.get("local_path", "")).name,
                resource_kind=item.get("resource_kind", "unknown"),
                size_bytes=item.get("size_bytes"),
                md5=item.get("md5"),
                sha256=item.get("sha256"),
                error_message=None,
            )
            for index, item in enumerate(payload.get("files", []), start=1)
        ]

    return []


def _serialize_resource(resource: DiscoveredResource) -> dict:
    return asdict(resource)


def _deserialize_resource(payload: dict) -> DiscoveredResource:
    return DiscoveredResource(**payload)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _downloaded_count(results: list[DownloadResult]) -> int:
    return sum(1 for result in results if result.status in {"success", "skipped"})


def _ignored_count(results: list[DownloadResult]) -> int:
    return sum(1 for result in results if result.status == "ignored")


def _print_stats(
    *,
    discovered: int,
    selected: int,
    downloaded: int,
    ignored: int,
    generated_pdf: Path | None,
) -> None:
    print(f"discovered: {discovered}")
    print(f"selected: {selected}")
    print(f"downloaded: {downloaded}")
    print(f"ignored: {ignored}")
    print(f"generated pdf path: {str(generated_pdf) if generated_pdf else '-'}")


def _parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "y", "on"}


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
