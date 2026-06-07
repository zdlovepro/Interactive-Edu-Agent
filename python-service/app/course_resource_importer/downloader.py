from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import aiohttp

from app.utils.logger import logger

from .authorized_fetcher import sanitize_headers_for_log
from .resource_models import DiscoveredResource

DownloadStatus = Literal["success", "failed", "skipped", "ignored"]
ALLOWED_DOWNLOAD_KINDS = frozenset({"slide_image", "courseware_file", "attachment", "content_image"})
RATE_LIMIT_LOCKS: dict[str, asyncio.Lock] = {}
RATE_LIMIT_NEXT_ALLOWED_AT: dict[str, float] = {}
DEFAULT_USER_AGENT = "Interactive-Edu-Agent Course Resource Downloader/1.0"


@dataclass(slots=True)
class DownloadPlan:
    task_id: str
    resources: list[DiscoveredResource]
    output_dir: Path
    selected_count: int
    ignored_count: int


@dataclass(slots=True)
class DownloadResult:
    resource_id: str
    url: str
    status: DownloadStatus
    local_path: str | None
    file_name: str
    resource_kind: str
    size_bytes: int | None
    md5: str | None
    sha256: str | None
    error_message: str | None


def build_download_plan(
    resources: list[DiscoveredResource],
    output_dir: Path,
    min_confidence: float = 0.6,
    include_unknown: bool = False,
) -> DownloadPlan:
    resolved_output_dir = output_dir.resolve()
    slide_resources = [resource for resource in resources if resource.resource_kind == "slide_image"]
    slide_name_map = _build_slide_file_name_map(slide_resources)

    planned_resources: list[DiscoveredResource] = []
    used_relative_paths: set[str] = set()
    selected_count = 0
    ignored_count = 0

    for resource in resources:
        selected = _should_download_resource(resource, min_confidence=min_confidence, include_unknown=include_unknown)
        updated_context = dict(resource.raw_context)
        updated_context["_download_selected"] = selected

        if selected:
            relative_path = _plan_relative_path(resource, slide_name_map, used_relative_paths)
            updated_context["_download_relative_path"] = relative_path.as_posix()
            updated_context["_download_subdir"] = relative_path.parent.as_posix()
            updated_context["_download_file_name"] = relative_path.name
            selected_count += 1
        else:
            ignored_count += 1

        planned_resources.append(replace(resource, raw_context=updated_context))

    return DownloadPlan(
        task_id=f"download_{uuid.uuid4().hex[:12]}",
        resources=planned_resources,
        output_dir=resolved_output_dir,
        selected_count=selected_count,
        ignored_count=ignored_count,
    )


async def download_plan(
    plan: DownloadPlan,
    cookie: str | None = None,
    authorization: str | None = None,
    referer: str | None = None,
    user_agent: str | None = None,
    concurrency: int = 3,
    rate_limit_per_host: float = 1.0,
) -> list[DownloadResult]:
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(max(1, concurrency))
    timeout = aiohttp.ClientTimeout(total=120)
    headers = _build_download_headers(cookie=cookie, authorization=authorization, referer=referer, user_agent=user_agent)

    logger.info(
        "Starting download plan. taskId=%s outputDir=%s selected=%s ignored=%s headers=%s",
        plan.task_id,
        str(plan.output_dir),
        plan.selected_count,
        plan.ignored_count,
        sanitize_headers_for_log(headers),
    )

    async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
        tasks = [
            asyncio.create_task(
                _download_or_ignore_resource(
                    resource=resource,
                    output_dir=plan.output_dir,
                    session=session,
                    semaphore=semaphore,
                    headers=headers,
                    rate_limit_per_host=rate_limit_per_host,
                )
            )
            for resource in plan.resources
        ]
        results = await asyncio.gather(*tasks)

    _write_manifest(plan, results)
    return results


async def _download_or_ignore_resource(
    *,
    resource: DiscoveredResource,
    output_dir: Path,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    headers: dict[str, str],
    rate_limit_per_host: float,
) -> DownloadResult:
    if not resource.raw_context.get("_download_selected"):
        return DownloadResult(
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

    async with semaphore:
        return await _download_resource(
            resource=resource,
            output_dir=output_dir,
            session=session,
            headers=headers,
            rate_limit_per_host=rate_limit_per_host,
        )


async def _download_resource(
    *,
    resource: DiscoveredResource,
    output_dir: Path,
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    rate_limit_per_host: float,
) -> DownloadResult:
    target_path = _resolve_target_path(output_dir, resource)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = target_path.with_name(f"{target_path.name}.part")

    if target_path.exists():
        size_bytes, md5_digest, sha256_digest = _compute_file_digests(target_path)
        return DownloadResult(
            resource_id=resource.resource_id,
            url=resource.url,
            status="skipped",
            local_path=str(target_path),
            file_name=target_path.name,
            resource_kind=resource.resource_kind,
            size_bytes=size_bytes,
            md5=md5_digest,
            sha256=sha256_digest,
            error_message=None,
        )

    host = urlsplit(resource.url).hostname or ""
    for attempt in range(1, 4):
        await _apply_rate_limit(host, rate_limit_per_host)

        range_headers = dict(headers)
        resume_bytes = part_path.stat().st_size if part_path.exists() else 0
        if resume_bytes > 0:
            range_headers["Range"] = f"bytes={resume_bytes}-"

        logger.info(
            "Downloading resource. resourceId=%s attempt=%s url=%s headers=%s",
            resource.resource_id,
            attempt,
            resource.url,
            sanitize_headers_for_log(range_headers),
        )

        try:
            async with session.get(resource.url, headers=range_headers, allow_redirects=True) as response:
                status = response.status

                if status in {401, 403}:
                    return _failed_result(resource, target_path.name, "未授权或登录已失效")
                if status == 404:
                    return _failed_result(resource, target_path.name, "资源不存在")
                if status == 429:
                    if attempt < 3:
                        await _sleep(2 ** (attempt - 1))
                        continue
                    return _failed_result(resource, target_path.name, "请求过于频繁，请稍后重试")
                if 500 <= status <= 599:
                    if attempt < 3:
                        await _sleep(2 ** (attempt - 1))
                        continue
                    return _failed_result(resource, target_path.name, "上游服务暂时不可用")
                if status >= 400:
                    return _failed_result(resource, target_path.name, f"下载失败，HTTP {status}")

                write_mode = "ab" if status == 206 and resume_bytes > 0 else "wb"
                if write_mode == "wb" and part_path.exists():
                    part_path.unlink()

                with part_path.open(write_mode) as file:
                    async for chunk in response.content.iter_chunked(65536):
                        if chunk:
                            file.write(chunk)

                part_path.replace(target_path)
                size_bytes, md5_digest, sha256_digest = _compute_file_digests(target_path)
                return DownloadResult(
                    resource_id=resource.resource_id,
                    url=resource.url,
                    status="success",
                    local_path=str(target_path),
                    file_name=target_path.name,
                    resource_kind=resource.resource_kind,
                    size_bytes=size_bytes,
                    md5=md5_digest,
                    sha256=sha256_digest,
                    error_message=None,
                )
        except asyncio.TimeoutError:
            if attempt < 3:
                await _sleep(2 ** (attempt - 1))
                continue
            return _failed_result(resource, target_path.name, "下载超时")
        except aiohttp.ClientError as exc:
            if attempt < 3:
                await _sleep(2 ** (attempt - 1))
                continue
            return _failed_result(resource, target_path.name, f"下载失败：{exc}")

    return _failed_result(resource, target_path.name, "下载失败")


def _should_download_resource(
    resource: DiscoveredResource,
    *,
    min_confidence: float,
    include_unknown: bool,
) -> bool:
    if resource.resource_kind in ALLOWED_DOWNLOAD_KINDS:
        return resource.confidence >= min_confidence
    if resource.resource_kind == "unknown" and include_unknown:
        return True
    return False


def _plan_relative_path(
    resource: DiscoveredResource,
    slide_name_map: dict[str, str],
    used_relative_paths: set[str],
) -> Path:
    subdir = _resource_subdir(resource.resource_kind)
    if resource.resource_kind == "slide_image":
        file_name = slide_name_map.get(resource.resource_id) or _sanitize_file_name(resource.file_name, fallback_stem="slide")
    else:
        fallback_stem = "attachment" if resource.resource_kind in {"courseware_file", "attachment", "unknown"} else "image"
        file_name = _sanitize_file_name(resource.file_name, fallback_stem=fallback_stem)

    relative_path = Path(subdir) / file_name
    relative_path = _dedupe_relative_path(relative_path, used_relative_paths)
    used_relative_paths.add(relative_path.as_posix())
    return relative_path


def _resource_subdir(resource_kind: str) -> str:
    if resource_kind == "slide_image":
        return "images"
    if resource_kind == "content_image":
        return "content_images"
    return "attachments"


def _build_slide_file_name_map(resources: list[DiscoveredResource]) -> dict[str, str]:
    ordered_resources = sorted(resources, key=_slide_sort_key)
    mapping: dict[str, str] = {}
    for index, resource in enumerate(ordered_resources, start=1):
        extension = resource.extension.lower().lstrip(".") or "png"
        mapping[resource.resource_id] = f"slide_{index:03d}.{extension}"
    return mapping


def _slide_sort_key(resource: DiscoveredResource) -> tuple[int, str]:
    number = _extract_trailing_number(resource.file_name)
    if number is not None:
        return (number, resource.file_name)
    return (10**9, resource.file_name)


def _extract_trailing_number(file_name: str) -> int | None:
    stem = Path(file_name).stem
    match = re.search(r"(\d+)$", stem)
    if not match:
        return None
    return int(match.group(1))


def _sanitize_file_name(file_name: str, *, fallback_stem: str) -> str:
    candidate = (file_name or "").replace("\\", "/").split("/")[-1].strip()
    if not candidate:
        return fallback_stem

    candidate = re.sub(r"[^\w.\- ]+", "_", candidate, flags=re.UNICODE)
    candidate = candidate.replace(" ", "_")
    candidate = candidate.strip("._")
    if not candidate:
        return fallback_stem

    return candidate


def _dedupe_relative_path(relative_path: Path, used_relative_paths: set[str]) -> Path:
    candidate = relative_path
    counter = 2
    while candidate.as_posix() in used_relative_paths:
        candidate = relative_path.with_name(f"{relative_path.stem}_{counter}{relative_path.suffix}")
        counter += 1
    return candidate


def _resolve_target_path(output_dir: Path, resource: DiscoveredResource) -> Path:
    relative_path_value = resource.raw_context.get("_download_relative_path")
    if not relative_path_value:
        relative_path = Path(_resource_subdir(resource.resource_kind)) / _sanitize_file_name(
            resource.file_name,
            fallback_stem="download",
        )
    else:
        relative_path = Path(str(relative_path_value))

    target_path = (output_dir / relative_path).resolve()
    output_dir_resolved = output_dir.resolve()
    try:
        target_path.relative_to(output_dir_resolved)
    except ValueError as exc:
        raise ValueError(f"Resolved target path escaped output directory: {target_path}") from exc
    return target_path


def _build_download_headers(
    *,
    cookie: str | None,
    authorization: str | None,
    referer: str | None,
    user_agent: str | None = None,
) -> dict[str, str]:
    headers = {"User-Agent": user_agent or DEFAULT_USER_AGENT}
    if cookie:
        headers["Cookie"] = cookie
    if authorization:
        headers["Authorization"] = authorization
    if referer:
        headers["Referer"] = referer
    return headers


def _failed_result(resource: DiscoveredResource, file_name: str, error_message: str) -> DownloadResult:
    return DownloadResult(
        resource_id=resource.resource_id,
        url=resource.url,
        status="failed",
        local_path=None,
        file_name=file_name,
        resource_kind=resource.resource_kind,
        size_bytes=None,
        md5=None,
        sha256=None,
        error_message=error_message,
    )


def _compute_file_digests(path: Path) -> tuple[int, str, str]:
    md5_digest = hashlib.md5()
    sha256_digest = hashlib.sha256()
    size_bytes = 0
    with path.open("rb") as file:
        while chunk := file.read(65536):
            size_bytes += len(chunk)
            md5_digest.update(chunk)
            sha256_digest.update(chunk)
    return size_bytes, md5_digest.hexdigest(), sha256_digest.hexdigest()


def _write_manifest(plan: DownloadPlan, results: list[DownloadResult]) -> None:
    manifest_path = plan.output_dir / "manifest.json"
    payload = {
        "task_id": plan.task_id,
        "selected_count": plan.selected_count,
        "ignored_count": plan.ignored_count,
        "results": [asdict(result) for result in results],
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def _apply_rate_limit(host: str, rate_limit_per_host: float) -> None:
    if not host or rate_limit_per_host <= 0:
        return

    interval_seconds = 1.0 / rate_limit_per_host
    host_lock = RATE_LIMIT_LOCKS.get(host)
    if host_lock is None:
        host_lock = asyncio.Lock()
        RATE_LIMIT_LOCKS[host] = host_lock

    async with host_lock:
        now = time.monotonic()
        next_allowed_at = RATE_LIMIT_NEXT_ALLOWED_AT.get(host, now)
        delay = max(0.0, next_allowed_at - now)
        if delay > 0:
            await _sleep(delay)
        RATE_LIMIT_NEXT_ALLOWED_AT[host] = max(next_allowed_at, time.monotonic()) + interval_seconds


async def _sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)
