from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.core.exceptions import AppException, BUSINESS_VALIDATION_FAILED
from app.course_resource_importer import ChaoxingCourseRef, build_chaoxing_course_url, parse_chaoxing_course_url
from app.schemas.chaoxing_import_task import (
    ChaoxingImportManifest,
    ChaoxingImportTaskCreateRequest,
    ChaoxingImportTaskView,
    ChaoxingManifestResource,
)
from app.schemas.course_resource_import import CourseResourceImportRequest
from app.services.course_resource_import_service import import_course_resources
from app.utils.logger import logger

_TASKS: dict[str, ChaoxingImportTaskView] = {}
_PUBLIC_MANIFEST_NAME = "chaoxing_task_manifest.json"


async def create_chaoxing_import_task(request: ChaoxingImportTaskCreateRequest) -> dict[str, object]:
    task_id = f"cx_{uuid.uuid4().hex[:12]}"
    output_dir = request.output_path or _default_output_dir(task_id)

    _store_task(
        ChaoxingImportTaskView(
            taskId=task_id,
            status="RUNNING",
            progress=20,
            message="Chaoxing import task is running",
        )
    )

    try:
        import_result = await import_course_resources(_to_import_request(request, output_dir))
        manifest = _build_public_manifest(task_id, request, import_result)
        public_manifest_path = output_dir / _PUBLIC_MANIFEST_NAME
        _write_public_manifest(public_manifest_path, manifest)

        task = ChaoxingImportTaskView(
            taskId=task_id,
            status="SUCCESS",
            progress=100,
            message="Chaoxing import completed",
            manifestPath=str(public_manifest_path),
            manifest=manifest,
        )
        _store_task(task)
        logger.info(
            "Chaoxing import task completed. taskId=%s resources=%s outputDir=%s",
            task_id,
            len(manifest.resources),
            output_dir,
        )
        return task.model_dump(by_alias=True)
    except Exception as exc:  # noqa: BLE001
        message = str(exc) if isinstance(exc, AppException) else "Chaoxing import failed"
        task = ChaoxingImportTaskView(
            taskId=task_id,
            status="FAILED",
            progress=100,
            message=message,
        )
        _store_task(task)
        logger.warning("Chaoxing import task failed. taskId=%s reason=%s", task_id, message)
        return task.model_dump(by_alias=True)


def get_chaoxing_import_task(task_id: str) -> dict[str, object]:
    task = _TASKS.get(task_id)
    if task is None:
        raise AppException(BUSINESS_VALIDATION_FAILED, "Chaoxing import task not found")
    return task.model_dump(by_alias=True)


def get_chaoxing_import_manifest(task_id: str) -> dict[str, object]:
    task = _TASKS.get(task_id)
    if task is None:
        raise AppException(BUSINESS_VALIDATION_FAILED, "Chaoxing import task not found")
    if task.manifest is not None:
        return task.manifest.model_dump(by_alias=True)
    if task.manifest_path:
        path = Path(task.manifest_path)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise AppException(BUSINESS_VALIDATION_FAILED, "Chaoxing import manifest is not ready")


def _to_import_request(request: ChaoxingImportTaskCreateRequest, output_dir: Path) -> CourseResourceImportRequest:
    url = request.url or _build_url_from_params(request)
    return CourseResourceImportRequest(
        sourceType=request.source_type,
        url=url,
        courseid=request.courseid,
        clazzid=request.clazzid,
        cpi=request.cpi,
        enc=request.enc,
        t=request.t,
        cookie=request.cookie,
        authorization=request.authorization,
        referer=request.referer,
        userAgent=request.user_agent,
        outputDir=str(output_dir),
        buildPdf=request.build_pdf,
    )


def _build_url_from_params(request: ChaoxingImportTaskCreateRequest) -> str | None:
    if not request.courseid:
        return None
    return build_chaoxing_course_url(
        ChaoxingCourseRef(
            courseid=request.courseid,
            clazzid=request.clazzid,
            cpi=request.cpi,
            enc=request.enc,
            t=request.t,
            referer=request.referer,
        )
    )


def _build_public_manifest(
    task_id: str,
    request: ChaoxingImportTaskCreateRequest,
    import_result: dict[str, object],
) -> ChaoxingImportManifest:
    course_ref = _resolve_course_ref(request)
    files = _load_manifest_files(import_result)
    resources = [_to_manifest_resource(file_item) for file_item in files]
    return ChaoxingImportManifest(
        taskId=task_id,
        courseId=course_ref.courseid if course_ref else request.courseid,
        clazzId=course_ref.clazzid if course_ref else request.clazzid,
        resources=resources,
    )


def _resolve_course_ref(request: ChaoxingImportTaskCreateRequest) -> ChaoxingCourseRef | None:
    if request.url:
        try:
            return parse_chaoxing_course_url(request.url)
        except Exception:  # noqa: BLE001
            return None
    if request.courseid:
        return ChaoxingCourseRef(
            courseid=request.courseid,
            clazzid=request.clazzid,
            cpi=request.cpi,
            enc=request.enc,
            t=request.t,
        )
    return None


def _load_manifest_files(import_result: dict[str, object]) -> list[dict[str, object]]:
    manifest_path = import_result.get("manifest_path")
    if not manifest_path:
        return []

    path = Path(str(manifest_path))
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    files = payload.get("files")
    return files if isinstance(files, list) else []


def _to_manifest_resource(file_item: dict[str, object]) -> ChaoxingManifestResource:
    resource_type = str(file_item.get("type") or Path(str(file_item.get("file_name") or "")).suffix.lstrip(".") or "unknown")
    local_path = str(file_item.get("local_path") or "") or None
    return ChaoxingManifestResource(
        resourceId=str(file_item.get("resource_id") or file_item.get("file_name") or uuid.uuid4().hex),
        title=str(file_item.get("title") or file_item.get("file_name") or "Untitled resource"),
        type=resource_type,
        sourceUrl=str(file_item.get("source_url") or "") or None,
        localPath=local_path,
        sha256=str(file_item.get("sha256") or "") or None,
        size=_safe_int(file_item.get("size")),
        parseReady=resource_type.lower() in {"ppt", "pptx", "pdf"},
    )


def _safe_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _write_public_manifest(path: Path, manifest: ChaoxingImportManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.model_dump(by_alias=True), ensure_ascii=False, indent=2), encoding="utf-8")


def _store_task(task: ChaoxingImportTaskView) -> None:
    _TASKS[task.task_id] = task


def _default_output_dir(task_id: str) -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "chaoxing-import" / task_id


def clear_chaoxing_import_tasks_for_test() -> None:
    _TASKS.clear()
