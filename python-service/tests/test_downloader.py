from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from app.course_resource_importer import downloader
from app.course_resource_importer.downloader import (
    DownloadPlan,
    build_download_plan,
    download_plan,
)
from app.course_resource_importer.resource_models import DiscoveredResource


class _FakeStream:
    def __init__(self, body: bytes):
        self._body = body

    async def iter_chunked(self, chunk_size: int):
        for index in range(0, len(self._body), chunk_size):
            yield self._body[index : index + chunk_size]


class _FakeResponse:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self.content = _FakeStream(body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeClientSession:
    def __init__(self, registry: dict[str, list[tuple[int, bytes]]], **kwargs):
        self.registry = {key: list(value) for key, value in registry.items()}
        self.calls: list[dict[str, object]] = []
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, headers=None, allow_redirects: bool = True):
        self.calls.append({"url": url, "headers": dict(headers or {}), "allow_redirects": allow_redirects})
        responses = self.registry.get(url)
        if not responses:
            raise AssertionError(f"No fake response registered for {url}")
        status, body = responses.pop(0)
        return _FakeResponse(status, body)


def test_build_download_plan_only_selects_downloadable_kinds(tmp_path: Path):
    resources = [
        _resource("slide", "slide_image", "1.png", confidence=0.9),
        _resource("ppt", "courseware_file", "lesson.pptx", confidence=0.99),
        _resource("doc", "attachment", "notes.docx", confidence=0.95),
        _resource("img", "content_image", "photo.png", confidence=0.7),
        _resource("ui", "ui_asset", "icon.png", confidence=0.95),
        _resource("unk", "unknown", "mystery.bin", confidence=0.8),
    ]

    plan = build_download_plan(resources, tmp_path)

    assert plan.selected_count == 4
    assert plan.ignored_count == 2
    selected_flags = {resource.resource_id: resource.raw_context["_download_selected"] for resource in plan.resources}
    assert selected_flags == {
        "slide": True,
        "ppt": True,
        "doc": True,
        "img": True,
        "ui": False,
        "unk": False,
    }


def test_include_unknown_true_selects_unknown(tmp_path: Path):
    resources = [_resource("unk", "unknown", "mystery.bin", confidence=0.1)]

    plan = build_download_plan(resources, tmp_path, include_unknown=True)

    assert plan.selected_count == 1
    assert plan.resources[0].raw_context["_download_selected"] is True


def test_download_plan_ignores_ui_asset_and_unknown_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    resources = [
        _resource("slide", "slide_image", "1.png", confidence=0.9),
        _resource("ui", "ui_asset", "icon.png", confidence=0.95),
        _resource("unk", "unknown", "mystery.bin", confidence=0.7),
    ]
    plan = build_download_plan(resources, tmp_path)
    registry = {"https://example.com/1.png": [(200, b"slide-bytes")]}
    fake_session = _install_fake_session(monkeypatch, registry)
    monkeypatch.setattr(downloader, "_sleep", _noop_sleep)

    results = asyncio.run(download_plan(plan, concurrency=2, rate_limit_per_host=1000.0))

    assert [result.status for result in results] == ["success", "ignored", "ignored"]
    assert len(fake_session.calls) == 1
    assert (tmp_path / "manifest.json").exists()


def test_download_plan_downloads_unknown_when_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    resources = [_resource("unk", "unknown", "mystery.bin", confidence=0.1)]
    plan = build_download_plan(resources, tmp_path, include_unknown=True)
    registry = {"https://example.com/mystery.bin": [(200, b"unknown-bytes")]}
    _install_fake_session(monkeypatch, registry)
    monkeypatch.setattr(downloader, "_sleep", _noop_sleep)

    results = asyncio.run(download_plan(plan, rate_limit_per_host=1000.0))

    assert results[0].status == "success"
    assert Path(results[0].local_path).exists()


def test_download_plan_returns_failed_on_403(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    plan = build_download_plan([_resource("ppt", "courseware_file", "lesson.pdf", confidence=0.99)], tmp_path)
    _install_fake_session(monkeypatch, {"https://example.com/lesson.pdf": [(403, b"")]})
    monkeypatch.setattr(downloader, "_sleep", _noop_sleep)

    results = asyncio.run(download_plan(plan, rate_limit_per_host=1000.0))

    assert results[0].status == "failed"
    assert results[0].error_message == "未授权或登录已失效"


def test_download_plan_returns_failed_on_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    plan = build_download_plan([_resource("ppt", "courseware_file", "lesson.pdf", confidence=0.99)], tmp_path)
    _install_fake_session(monkeypatch, {"https://example.com/lesson.pdf": [(404, b"")]})
    monkeypatch.setattr(downloader, "_sleep", _noop_sleep)

    results = asyncio.run(download_plan(plan, rate_limit_per_host=1000.0))

    assert results[0].status == "failed"
    assert results[0].error_message == "资源不存在"


def test_download_plan_retries_on_500(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    plan = build_download_plan([_resource("ppt", "courseware_file", "lesson.pdf", confidence=0.99)], tmp_path)
    fake_session = _install_fake_session(
        monkeypatch,
        {"https://example.com/lesson.pdf": [(500, b""), (500, b""), (200, b"pdf-body")]},
    )
    monkeypatch.setattr(downloader, "_sleep", _noop_sleep)

    results = asyncio.run(download_plan(plan, rate_limit_per_host=1000.0))

    assert results[0].status == "success"
    assert len(fake_session.calls) == 3


def test_download_plan_resumes_from_part_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    plan = build_download_plan([_resource("ppt", "courseware_file", "lesson.pdf", confidence=0.99)], tmp_path)
    planned_resource = plan.resources[0]
    final_path = Path(planned_resource.raw_context["_download_relative_path"])
    part_path = tmp_path / final_path.parent / f"{final_path.name}.part"
    part_path.parent.mkdir(parents=True, exist_ok=True)
    part_path.write_bytes(b"hello ")

    fake_session = _install_fake_session(monkeypatch, {"https://example.com/lesson.pdf": [(206, b"world")]})
    monkeypatch.setattr(downloader, "_sleep", _noop_sleep)

    results = asyncio.run(download_plan(plan, rate_limit_per_host=1000.0))

    assert results[0].status == "success"
    assert Path(results[0].local_path).read_bytes() == b"hello world"
    assert fake_session.calls[0]["headers"]["Range"] == "bytes=6-"


def test_download_plan_computes_md5_and_sha256(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    payload = b"digest-me"
    plan = build_download_plan([_resource("ppt", "courseware_file", "lesson.pdf", confidence=0.99)], tmp_path)
    _install_fake_session(monkeypatch, {"https://example.com/lesson.pdf": [(200, payload)]})
    monkeypatch.setattr(downloader, "_sleep", _noop_sleep)

    results = asyncio.run(download_plan(plan, rate_limit_per_host=1000.0))

    assert results[0].md5 == hashlib.md5(payload).hexdigest()
    assert results[0].sha256 == hashlib.sha256(payload).hexdigest()


def test_download_plan_does_not_escape_output_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    resource = _resource("ppt", "courseware_file", "../../escape.pdf", confidence=0.99)
    plan = build_download_plan([resource], tmp_path)
    _install_fake_session(monkeypatch, {"https://example.com/../../escape.pdf": [(200, b"safe")]})
    monkeypatch.setattr(downloader, "_sleep", _noop_sleep)

    results = asyncio.run(download_plan(plan, rate_limit_per_host=1000.0))

    local_path = Path(results[0].local_path).resolve()
    assert str(local_path).startswith(str(tmp_path.resolve()))
    assert local_path.name == "escape.pdf"


def _install_fake_session(monkeypatch: pytest.MonkeyPatch, registry: dict[str, list[tuple[int, bytes]]]) -> _FakeClientSession:
    session = _FakeClientSession(registry)

    def factory(**kwargs):
        session.kwargs = kwargs
        return session

    monkeypatch.setattr(downloader.aiohttp, "ClientSession", factory)
    return session


def _resource(
    resource_id: str,
    resource_kind: str,
    file_name: str,
    *,
    confidence: float,
) -> DiscoveredResource:
    return DiscoveredResource(
        resource_id=resource_id,
        url=f"https://example.com/{file_name}",
        file_name=file_name,
        extension=Path(file_name).suffix.lstrip("."),
        source_type="html",
        resource_kind=resource_kind,
        confidence=confidence,
        raw_context={},
    )


async def _noop_sleep(_seconds: float) -> None:
    return None
