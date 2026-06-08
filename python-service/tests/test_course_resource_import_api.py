from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

from app.api.v1 import course_resource_import as course_resource_import_api
from app.main import app
from app.services import vector_store as vector_store_module

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _StartupVectorStoreStub:
    backend_name = "test_stub"


@pytest.fixture
def request_app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vector_store_module, "get_vector_store", lambda: _StartupVectorStoreStub())

    def _request(method: str, path: str, **kwargs):
        async def _run():
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(_run())

    return _request


def test_discover_endpoint_returns_resources(request_app, monkeypatch):
    async def fake_discover(_request):
        return {
            "resources": [
                {
                    "resource_id": "slide_1",
                    "platform": "chaoxing",
                    "source_type": "html",
                    "source_url": "https://mooc2-ans.chaoxing.com/course",
                    "url": "https://p.ananas.chaoxing.com/slide_001.png",
                    "title": "Machine Learning",
                    "file_name": "slide_001.png",
                    "extension": "png",
                    "mime_type": "image/png",
                    "courseid": "260728285",
                    "clazzid": "139811358",
                    "chapter_id": None,
                    "object_id": None,
                    "expected_size": None,
                    "expected_md5": None,
                    "resource_kind": "slide_image",
                    "confidence": 0.92,
                    "reason": "large 16:9 image likely slide page",
                    "raw_context": {},
                }
            ],
            "summary": {
                "discovered": 1,
                "selected": 1,
                "ignored": 0,
            },
        }

    monkeypatch.setattr(course_resource_import_api, "discover_course_resources", fake_discover)

    response = request_app(
        "POST",
        "/python/v1/course-resource-import/discover",
        json={
            "source_type": "CHAOXING_COURSE",
            "url": "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
            "cookie": "secret-cookie",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["summary"] == {
        "discovered": 1,
        "selected": 1,
        "ignored": 0,
    }
    assert body["data"]["resources"][0]["resource_kind"] == "slide_image"


def test_download_endpoint_returns_manifest_paths(request_app, monkeypatch):
    async def fake_download(_request):
        return {
            "manifest_path": "data/course-import/import_xxx/manifest.json",
            "parse_ready_manifest_path": "data/course-import/import_xxx/parse_ready_manifest.json",
            "generated_pdf": "data/course-import/import_xxx/courseware_from_images.pdf",
            "summary": {
                "downloaded": 18,
                "failed": 0,
                "ignored": 102,
            },
        }

    monkeypatch.setattr(course_resource_import_api, "download_course_resources", fake_download)

    response = request_app(
        "POST",
        "/python/v1/course-resource-import/download",
        json={
            "task_id": "import_xxx",
            "resources": [],
            "headers": {"cookie": "secret-cookie", "referer": "https://mooc2-ans.chaoxing.com/"},
            "output_dir": "data/course-import/import_xxx",
            "build_pdf": True,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["manifest_path"].endswith("manifest.json")
    assert body["data"]["generated_pdf"].endswith("courseware_from_images.pdf")
    assert body["data"]["summary"]["downloaded"] == 18


def test_import_endpoint_accepts_camel_case_fields(request_app, monkeypatch):
    captured = {}

    async def fake_import(request):
        captured["source_type"] = request.source_type
        captured["output_dir"] = request.output_dir
        captured["build_pdf"] = request.build_pdf
        return {
            "manifest_path": "data/course-import/import_xxx/manifest.json",
            "parse_ready_manifest_path": "data/course-import/import_xxx/parse_ready_manifest.json",
            "generated_pdf": None,
            "summary": {
                "downloaded": 1,
                "failed": 0,
                "ignored": 0,
            },
        }

    monkeypatch.setattr(course_resource_import_api, "import_course_resources", fake_import)

    response = request_app(
        "POST",
        "/python/v1/course-resource-import/import",
        json={
            "sourceType": "CHAOXING_COURSE",
            "url": "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
            "cookie": "secret-cookie",
            "outputDir": "data/course-import/import_xxx",
            "buildPdf": True,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert captured == {
        "source_type": "CHAOXING_COURSE",
        "output_dir": "data/course-import/import_xxx",
        "build_pdf": True,
    }


def test_discover_requires_explicit_authorization(request_app):
    response = request_app(
        "POST",
        "/python/v1/course-resource-import/discover",
        json={
            "source_type": "CHAOXING_COURSE",
            "url": "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 40002
    assert body["data"] is None
    assert "Cookie, Authorization, or auth_session_id" in body["message"]


def test_discover_rejects_non_chaoxing_url(request_app):
    response = request_app(
        "POST",
        "/python/v1/course-resource-import/discover",
        json={
            "source_type": "CHAOXING_COURSE",
            "url": "https://example.com/course?id=1",
            "cookie": "secret-cookie",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 40001
    assert body["data"] is None
    assert "chaoxing.com" in body["message"]
