from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .downloader import DownloadResult
from .pdf_builder import build_pdf_from_slide_images, select_slide_images_from_results


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    should_build_pdf = args.command == "build-pdf" or _parse_bool(args.build_pdf)
    if not should_build_pdf:
        parser.print_help()
        return 1

    if not args.manifest or not args.output:
        parser.error("--manifest and --output are required when building a PDF")

    manifest_path = Path(args.manifest)
    output_path = Path(args.output)
    results = _load_results_from_manifest(manifest_path)
    slide_images = select_slide_images_from_results(results)
    built_pdf = build_pdf_from_slide_images(slide_images, output_path, title=args.title)
    print(str(built_pdf))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.course_resource_importer.cli")
    parser.add_argument("--build-pdf", default="false")
    parser.add_argument("--manifest")
    parser.add_argument("--output")
    parser.add_argument("--title")

    subparsers = parser.add_subparsers(dest="command")
    pdf_parser = subparsers.add_parser("build-pdf")
    pdf_parser.add_argument("--manifest", required=True)
    pdf_parser.add_argument("--output", required=True)
    pdf_parser.add_argument("--title")

    return parser


def _load_results_from_manifest(manifest_path: Path) -> list[DownloadResult]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = payload.get("results", [])
    return [DownloadResult(**item) for item in items]


def _parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "y", "on"}


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
