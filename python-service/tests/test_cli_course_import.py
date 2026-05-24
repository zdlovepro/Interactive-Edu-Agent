from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from app.course_resource_importer import cli
from app.course_resource_importer.downloader import DownloadResult
from app.course_resource_importer.models import AuthorizedFetchContext
from app.course_resource_importer.resource_models import DiscoveredResource


def test_import_chaoxing_course_from_url_creates_manifests(tmp_path: Path, monkeypatch, capsys):
    output_dir = tmp_path / "260728285"
    course_url = (
        "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu"
        "?courseid=260728285&clazzid=139811358&cpi=356891153&enc=abc&pageHeader=0&v=0&hideHead=0"
    )
    slide_resource, ppt_resource = _classified_resources()

    async def fake_fetch(url: str, context: AuthorizedFetchContext) -> str:
        assert url == course_url
        assert context.cookie == "secret-cookie"
        return "<html></html>"

    monkeypatch.setattr(cli, "fetch_authorized_html", fake_fetch)
    monkeypatch.setattr(cli, "discover_resources_from_html", lambda html, page_url=None, course_ref=None: [slide_resource, ppt_resource])
    monkeypatch.setattr(cli, "classify_resources", lambda resources: resources)
    monkeypatch.setattr(cli, "download_plan", _fake_download_plan_factory(output_dir))

    exit_code = cli.main(
        [
            "import-chaoxing-course",
            "--url",
            course_url,
            "--cookie",
            "secret-cookie",
            "--output-dir",
            str(output_dir),
            "--build-pdf",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "secret-cookie" not in captured.out
    assert "secret-cookie" not in captured.err
    assert (output_dir / "resources.raw.json").exists()
    assert (output_dir / "resources.classified.json").exists()
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "parse_ready_manifest.json").exists()
    assert (output_dir / "courseware_from_images.pdf").exists()

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["courseid"] == "260728285"
    assert manifest["selected_count"] == 2
    assert manifest["downloaded_count"] == 2
    assert manifest["generated"]["pdf_from_slide_images"].endswith("courseware_from_images.pdf")

    parse_ready = json.loads((output_dir / "parse_ready_manifest.json").read_text(encoding="utf-8"))
    assert parse_ready["parse_ready_files"][0]["type"] == "pdf"
    assert any(item["type"] == "courseware_file" for item in parse_ready["parse_ready_files"])
    assert "discovered: 2" in captured.out


def test_import_chaoxing_course_from_params_builds_url(tmp_path: Path, monkeypatch):
    output_dir = tmp_path / "260728285"
    captured: dict[str, str] = {}

    async def fake_fetch(url: str, context: AuthorizedFetchContext) -> str:
        captured["url"] = url
        captured["referer"] = context.referer or ""
        return "<html></html>"

    monkeypatch.setattr(cli, "fetch_authorized_html", fake_fetch)
    monkeypatch.setattr(cli, "discover_resources_from_html", lambda html, page_url=None, course_ref=None: [])
    monkeypatch.setattr(cli, "classify_resources", lambda resources: resources)
    monkeypatch.setattr(cli, "download_plan", _fake_download_plan_factory(output_dir))

    exit_code = cli.main(
        [
            "import-chaoxing-course",
            "--courseid",
            "260728285",
            "--clazzid",
            "139811358",
            "--cpi",
            "356891153",
            "--enc",
            "2448a3080846a1ab7a7c597107a9c576",
            "--cookie",
            "secret-cookie",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert captured["url"].startswith("https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?")
    assert "courseid=260728285" in captured["url"]
    assert "clazzid=139811358" in captured["url"]
    assert "cpi=356891153" in captured["url"]
    assert "enc=2448a3080846a1ab7a7c597107a9c576" in captured["url"]


def test_discover_command_writes_resources_json(tmp_path: Path, monkeypatch):
    output_json = tmp_path / "resources.json"
    slide_resource, ppt_resource = _classified_resources()

    async def fake_fetch(url: str, context: AuthorizedFetchContext) -> str:
        return "<html></html>"

    monkeypatch.setattr(cli, "fetch_authorized_html", fake_fetch)
    monkeypatch.setattr(cli, "discover_resources_from_html", lambda html, page_url=None, course_ref=None: [slide_resource, ppt_resource])
    monkeypatch.setattr(cli, "classify_resources", lambda resources: resources)

    exit_code = cli.main(
        [
            "discover",
            "--url",
            "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
            "--cookie",
            "secret-cookie",
            "--output",
            str(output_json),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["resource_count"] == 2
    assert len(payload["resources"]) == 2
    assert payload["resources"][0]["resource_kind"] in {"slide_image", "courseware_file"}


def test_download_command_reads_resources_and_writes_manifest(tmp_path: Path, monkeypatch):
    output_dir = tmp_path / "260728285"
    slide_resource, ppt_resource = _classified_resources()
    resources_json = tmp_path / "resources.json"
    resources_json.write_text(
        json.dumps(
            {
                "source": "chaoxing_authorized_course_discovery",
                "courseid": "260728285",
                "clazzid": "139811358",
                "page_url": "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
                "resources": [as_payload(slide_resource), as_payload(ppt_resource)],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "download_plan", _fake_download_plan_factory(output_dir))

    exit_code = cli.main(
        [
            "download",
            "--resources",
            str(resources_json),
            "--output-dir",
            str(output_dir),
            "--build-pdf",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["selected_count"] == 2
    assert manifest["downloaded_count"] == 2
    assert (output_dir / "parse_ready_manifest.json").exists()
    assert (output_dir / "courseware_from_images.pdf").exists()


def test_cli_returns_non_zero_on_failure(tmp_path: Path, monkeypatch, capsys):
    async def fake_fetch(url: str, context: AuthorizedFetchContext) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "fetch_authorized_html", fake_fetch)

    exit_code = cli.main(
        [
            "discover",
            "--url",
            "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
            "--cookie",
            "secret-cookie",
            "--output",
            str(tmp_path / "resources.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "boom" in captured.err
    assert "secret-cookie" not in captured.err


def _classified_resources() -> tuple[DiscoveredResource, DiscoveredResource]:
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
    ppt_resource = DiscoveredResource(
        resource_id="ppt-1",
        url="https://example.com/original.pptx",
        title="Original PPT",
        file_name="original.pptx",
        extension="pptx",
        source_type="html",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        courseid="260728285",
        clazzid="139811358",
        resource_kind="courseware_file",
        confidence=0.98,
        reason="extension .pptx recognized as courseware file",
        raw_context={"tag": "a"},
    )
    return slide_resource, ppt_resource


def as_payload(resource: DiscoveredResource) -> dict:
    return {
        "resource_id": resource.resource_id,
        "platform": resource.platform,
        "source_type": resource.source_type,
        "source_url": resource.source_url,
        "url": resource.url,
        "title": resource.title,
        "file_name": resource.file_name,
        "extension": resource.extension,
        "mime_type": resource.mime_type,
        "courseid": resource.courseid,
        "clazzid": resource.clazzid,
        "chapter_id": resource.chapter_id,
        "object_id": resource.object_id,
        "expected_size": resource.expected_size,
        "expected_md5": resource.expected_md5,
        "resource_kind": resource.resource_kind,
        "confidence": resource.confidence,
        "reason": resource.reason,
        "raw_context": resource.raw_context,
    }


def _fake_download_plan_factory(output_dir: Path):
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
                local_path.write_bytes(b"pptx-bytes")

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
