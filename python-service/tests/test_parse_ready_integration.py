from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from app.course_resource_importer import cli
from app.course_resource_importer.downloader import DownloadResult
from app.course_resource_importer.models import AuthorizedFetchContext
from app.course_resource_importer.parse_ready import load_parse_ready_files
from app.course_resource_importer.resource_models import DiscoveredResource


def test_load_parse_ready_files_reads_paths_in_order(tmp_path: Path):
    pdf_path = tmp_path / "courseware_from_images.pdf"
    pptx_path = tmp_path / "original.pptx"
    pdf_path.write_bytes(b"%PDF-1.4")
    pptx_path.write_bytes(b"pptx")

    manifest_path = tmp_path / "parse_ready_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source": "chaoxing_authorized_course_import",
                "parse_ready_files": [
                    {"type": "pdf", "path": str(pdf_path), "title": "Merged PDF"},
                    {"type": "courseware_file", "path": str(pptx_path), "title": "Original PPTX"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = load_parse_ready_files(manifest_path)

    assert loaded == [pdf_path.resolve(), pptx_path.resolve()]


def test_import_and_parse_calls_existing_parse_flow(tmp_path: Path, monkeypatch):
    output_dir = tmp_path / "260728285"
    course_url = "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285"
    slide_resource, pptx_resource = _resources_for_import("pptx")
    captured_requests: list[tuple[str, str]] = []

    async def fake_fetch(url: str, context: AuthorizedFetchContext) -> str:
        return "<html></html>"

    def fake_parse_courseware_file(request):
        captured_requests.append((request.file_path, request.file_name))
        return {"pages": 1, "outline": [request.file_name], "segments": []}

    monkeypatch.setattr(cli, "fetch_authorized_html", fake_fetch)
    monkeypatch.setattr(cli, "discover_resources_from_html", lambda html, page_url=None, course_ref=None: [slide_resource, pptx_resource])
    monkeypatch.setattr(cli, "classify_resources", lambda resources: resources)
    monkeypatch.setattr(cli, "download_plan", _fake_download_plan_factory(output_dir, courseware_extension="pptx"))
    monkeypatch.setattr(cli, "parse_courseware_file", fake_parse_courseware_file)

    exit_code = cli.main(
        [
            "import-and-parse",
            "--url",
            course_url,
            "--cookie",
            "secret-cookie",
            "--output-dir",
            str(output_dir),
            "--build-pdf",
        ]
    )

    assert exit_code == 0
    parsed_names = [file_name for _, file_name in captured_requests]
    assert "courseware_from_images.pdf" in parsed_names
    assert "original.pptx" in parsed_names

    parse_results = json.loads((output_dir / "parse_results.json").read_text(encoding="utf-8"))
    assert parse_results["parsed_count"] == 2
    assert parse_results["todo_count"] == 0
    assert all(item["status"] == "success" for item in parse_results["files"])


def test_import_and_parse_marks_ppt_as_todo(tmp_path: Path, monkeypatch):
    output_dir = tmp_path / "260728285"
    slide_resource, ppt_resource = _resources_for_import("ppt")

    async def fake_fetch(url: str, context: AuthorizedFetchContext) -> str:
        return "<html></html>"

    def fake_parse_courseware_file(request):
        return {"pages": 1, "outline": [request.file_name], "segments": []}

    monkeypatch.setattr(cli, "fetch_authorized_html", fake_fetch)
    monkeypatch.setattr(cli, "discover_resources_from_html", lambda html, page_url=None, course_ref=None: [slide_resource, ppt_resource])
    monkeypatch.setattr(cli, "classify_resources", lambda resources: resources)
    monkeypatch.setattr(cli, "download_plan", _fake_download_plan_factory(output_dir, courseware_extension="ppt"))
    monkeypatch.setattr(cli, "parse_courseware_file", fake_parse_courseware_file)

    exit_code = cli.main(
        [
            "import-and-parse",
            "--courseid",
            "260728285",
            "--cookie",
            "secret-cookie",
            "--output-dir",
            str(output_dir),
            "--build-pdf",
        ]
    )

    assert exit_code == 0
    parse_results = json.loads((output_dir / "parse_results.json").read_text(encoding="utf-8"))
    assert parse_results["parsed_count"] == 1
    assert parse_results["todo_count"] == 1
    assert any(item["status"] == "todo" for item in parse_results["files"])
    assert any("supports only .pdf and .pptx" in item.get("message", "") for item in parse_results["files"])


def _resources_for_import(courseware_extension: str) -> tuple[DiscoveredResource, DiscoveredResource]:
    slide_resource = DiscoveredResource(
        resource_id="slide-1",
        url="https://example.com/slide_001.png",
        title="Machine Learning Cover",
        file_name="slide_001.png",
        extension="png",
        source_type="html",
        mime_type="image/png",
        courseid="260728285",
        clazzid="139811358",
        resource_kind="slide_image",
        confidence=0.92,
        reason="large 16:9 image likely slide page",
        raw_context={"tag": "img"},
    )
    courseware_resource = DiscoveredResource(
        resource_id="courseware-1",
        url=f"https://example.com/original.{courseware_extension}",
        title="Original Courseware",
        file_name=f"original.{courseware_extension}",
        extension=courseware_extension,
        source_type="html",
        mime_type="application/octet-stream",
        courseid="260728285",
        clazzid="139811358",
        resource_kind="courseware_file",
        confidence=0.98,
        reason=f"extension .{courseware_extension} recognized as courseware file",
        raw_context={"tag": "a"},
    )
    return slide_resource, courseware_resource


def _fake_download_plan_factory(output_dir: Path, *, courseware_extension: str):
    async def fake_download_plan(
        plan,
        cookie: str | None = None,
        authorization: str | None = None,
        referer: str | None = None,
        concurrency: int = 3,
        rate_limit_per_host: float = 1.0,
    ):
        results: list[DownloadResult] = []
        for resource in plan.resources:
            if not resource.raw_context.get("_download_selected"):
                results.append(
                    DownloadResult(
                        resource_id=resource.resource_id,
                        url=resource.url,
                        status="ignored",
                        local_path=None,
                        file_name=resource.file_name,
                        resource_kind=resource.resource_kind,
                        size_bytes=None,
                        md5=None,
                        sha256=None,
                        error_message=None,
                    )
                )
                continue

            relative_path = Path(resource.raw_context["_download_relative_path"])
            local_path = output_dir / relative_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            if resource.resource_kind == "slide_image":
                Image.new("RGB", (1280, 720), "red").save(local_path)
            else:
                local_path.write_bytes(f"{courseware_extension}-bytes".encode("utf-8"))

            results.append(
                DownloadResult(
                    resource_id=resource.resource_id,
                    url=resource.url,
                    status="success",
                    local_path=str(local_path),
                    file_name=local_path.name,
                    resource_kind=resource.resource_kind,
                    size_bytes=local_path.stat().st_size,
                    md5="md5",
                    sha256="sha256",
                    error_message=None,
                )
            )
        return results

    return fake_download_plan
