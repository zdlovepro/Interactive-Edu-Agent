from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings
from app.core.exceptions import AppException, BUSINESS_VALIDATION_FAILED, DOWNSTREAM_SERVICE_ERROR, PARAM_ERROR
from app.course_resource_importer.config import DEFAULT_USER_AGENT
from app.course_resource_importer.errors import UnauthorizedFetchError
from app.utils.logger import logger

try:  # pragma: no cover - exercised in real auth runtime.
    from playwright.async_api import Browser, BrowserContext, Page, async_playwright
except ImportError:  # pragma: no cover - keeps non-auth endpoints importable.
    Browser = Any
    BrowserContext = Any
    Page = Any
    async_playwright = None

try:  # pragma: no cover - real Redis is used in full mode.
    import redis.asyncio as redis_async
except ImportError:  # pragma: no cover - local fallback without Redis package.
    redis_async = None


STATUS_CREATED = "CREATED"
STATUS_WAITING_QR = "WAITING_QR"
STATUS_WAITING_SCAN = "WAITING_SCAN"
STATUS_AUTHORIZED = "AUTHORIZED"
STATUS_EXPIRED = "EXPIRED"
STATUS_FAILED = "FAILED"
STATUS_CLOSED = "CLOSED"

_COOKIE_NAMES_REQUIRED = {"_uid"}
_COOKIE_NAMES_SECONDARY = {"vc", "fid", "uf"}
_SESSION_PREFIX = "chaoxing:auth:"
_REDACTED = "<redacted>"


@dataclass(slots=True)
class _RuntimeSession:
    session_id: str
    status: str = STATUS_CREATED
    message: str | None = None
    qr_code_png: bytes | None = None
    cookie_header: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC) + timedelta(seconds=settings.CHAOXING_AUTH_TTL_SECONDS))
    authorized_at: datetime | None = None
    playwright: Any | None = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    poll_task: asyncio.Task | None = None


class ChaoxingAuthSessionStore:
    def __init__(self) -> None:
        self._memory: dict[str, dict[str, Any]] = {}
        self._redis_client: Any | None = None
        self._redis_checked = False

    async def save_public_state(self, session: _RuntimeSession) -> None:
        payload = {
            "session_id": session.session_id,
            "status": session.status,
            "message": session.message,
            "expires_at": _iso(session.expires_at),
            "authorized_at": _iso(session.authorized_at),
        }
        await self._set_json(session.session_id, "state", payload)

    async def save_qrcode(self, session_id: str, qrcode_png: bytes) -> None:
        await self._set_json(session_id, "qrcode", {"png": base64.b64encode(qrcode_png).decode("ascii")})

    async def get_qrcode(self, session_id: str) -> bytes | None:
        payload = await self._get_json(session_id, "qrcode")
        encoded = payload.get("png") if isinstance(payload, dict) else None
        if not encoded:
            return None
        try:
            return base64.b64decode(encoded)
        except Exception:  # noqa: BLE001
            return None

    async def save_cookie(self, session_id: str, cookie_header: str) -> None:
        await self._set_json(session_id, "cookie", {"cookie": cookie_header})

    async def get_cookie(self, session_id: str) -> str | None:
        payload = await self._get_json(session_id, "cookie")
        cookie = payload.get("cookie") if isinstance(payload, dict) else None
        return str(cookie) if cookie else None

    async def get_public_state(self, session_id: str) -> dict[str, Any] | None:
        return await self._get_json(session_id, "state")

    async def delete(self, session_id: str) -> None:
        redis_client = await self._redis()
        keys = [self._key(session_id, suffix) for suffix in ("state", "qrcode", "cookie")]
        if redis_client is not None:
            await redis_client.delete(*keys)
        for key in keys:
            self._memory.pop(key, None)

    async def _set_json(self, session_id: str, suffix: str, payload: dict[str, Any]) -> None:
        key = self._key(session_id, suffix)
        text = json.dumps(payload, ensure_ascii=False)
        redis_client = await self._redis()
        if redis_client is not None:
            await redis_client.set(key, text, ex=settings.CHAOXING_AUTH_TTL_SECONDS)
            return
        self._memory[key] = {"payload": payload, "expires_at": time.monotonic() + settings.CHAOXING_AUTH_TTL_SECONDS}

    async def _get_json(self, session_id: str, suffix: str) -> dict[str, Any] | None:
        key = self._key(session_id, suffix)
        redis_client = await self._redis()
        if redis_client is not None:
            raw = await redis_client.get(key)
            if not raw:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)

        entry = self._memory.get(key)
        if not entry:
            return None
        if float(entry.get("expires_at", 0)) < time.monotonic():
            self._memory.pop(key, None)
            return None
        payload = entry.get("payload")
        return payload if isinstance(payload, dict) else None

    async def _redis(self) -> Any | None:
        if self._redis_checked:
            return self._redis_client
        self._redis_checked = True
        if redis_async is None:
            return None

        redis_url = settings.REDIS_URL.strip()
        try:
            if redis_url:
                self._redis_client = redis_async.from_url(redis_url, decode_responses=True)
            else:
                self._redis_client = redis_async.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DATABASE,
                    password=settings.REDIS_PASSWORD or None,
                    decode_responses=True,
                )
            await self._redis_client.ping()
            logger.info("Chaoxing auth session store uses Redis.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable for Chaoxing auth sessions; falling back to in-memory store. reason=%s", exc)
            self._redis_client = None
        return self._redis_client

    @staticmethod
    def _key(session_id: str, suffix: str) -> str:
        return f"{_SESSION_PREFIX}{session_id}:{suffix}"


class ChaoxingAuthService:
    def __init__(self) -> None:
        self._store = ChaoxingAuthSessionStore()
        self._sessions: dict[str, _RuntimeSession] = {}

    async def create_session(self, *, course_url: str | None = None, user_agent: str | None = None) -> dict[str, Any]:
        if async_playwright is None:
            raise AppException(DOWNSTREAM_SERVICE_ERROR, "Playwright is not installed in python-service.")

        session_id = "cx_auth_" + uuid.uuid4().hex
        session = _RuntimeSession(session_id=session_id)
        self._sessions[session_id] = session
        await self._set_status(session, STATUS_WAITING_QR, "Opening Chaoxing QR login page.")

        try:
            session.playwright = await async_playwright().start()
            session.browser = await session.playwright.chromium.launch(
                headless=settings.CHAOXING_AUTH_HEADLESS,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            session.context = await session.browser.new_context(user_agent=(user_agent or DEFAULT_USER_AGENT))
            session.page = await session.context.new_page()
            await session.page.goto(settings.CHAOXING_AUTH_LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
            await session.page.wait_for_timeout(1200)
            session.qr_code_png = await _capture_qr_code(session.page)
            await self._store.save_qrcode(session_id, session.qr_code_png)
            await self._set_status(session, STATUS_WAITING_SCAN, "Waiting for Learning App QR confirmation.")
            session.poll_task = asyncio.create_task(self._poll_until_authorized(session, course_url=course_url))
            return self._public_payload(session)
        except Exception as exc:  # noqa: BLE001
            await self._set_status(session, STATUS_FAILED, f"Failed to open Chaoxing QR login: {exc}")
            await self._close_runtime(session)
            raise AppException(DOWNSTREAM_SERVICE_ERROR, "Failed to create Chaoxing auth session.") from exc

    async def get_session(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is not None:
            return self._public_payload(session)

        stored = await self._store.get_public_state(session_id)
        if stored is None:
            raise AppException(PARAM_ERROR, "Chaoxing auth session not found or expired.")
        stored["qr_code_url"] = f"/python/v1/chaoxing/auth/sessions/{session_id}/qrcode"
        return stored

    async def get_qrcode(self, session_id: str) -> bytes:
        session = self._sessions.get(session_id)
        if session is not None and session.qr_code_png:
            return session.qr_code_png

        qrcode = await self._store.get_qrcode(session_id)
        if not qrcode:
            raise AppException(PARAM_ERROR, "Chaoxing auth QR code not found or expired.")
        return qrcode

    async def get_cookie_header(self, session_id: str) -> str:
        session = self._sessions.get(session_id)
        if session is not None and session.cookie_header:
            return session.cookie_header

        cookie = await self._store.get_cookie(session_id)
        if not cookie:
            raise UnauthorizedFetchError("Chaoxing auth session is not authorized or has expired.")
        return cookie

    async def close_session(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            if session.poll_task:
                session.poll_task.cancel()
            await self._set_status(session, STATUS_CLOSED, "Chaoxing auth session closed.")
            await self._close_runtime(session)
        await self._store.delete(session_id)
        return {
            "session_id": session_id,
            "status": STATUS_CLOSED,
            "message": "Chaoxing auth session closed.",
            "qr_code_url": None,
            "expires_at": None,
            "authorized_at": None,
        }

    async def _poll_until_authorized(self, session: _RuntimeSession, *, course_url: str | None) -> None:
        deadline = time.monotonic() + settings.CHAOXING_AUTH_TIMEOUT_SECONDS
        try:
            while time.monotonic() < deadline:
                if session.context is None:
                    break
                cookies = await session.context.cookies()
                if _is_authorized_cookie_set(cookies):
                    cookie_header = _build_cookie_header(cookies)
                    session.cookie_header = cookie_header
                    session.authorized_at = datetime.now(UTC)
                    await self._store.save_cookie(session.session_id, cookie_header)
                    await self._set_status(session, STATUS_AUTHORIZED, "Chaoxing authorization succeeded.")
                    logger.info("Chaoxing auth session authorized. sessionId=%s cookie=%s", session.session_id, _REDACTED)
                    await self._close_runtime(session)
                    return

                if session.page is not None and course_url and session.page.url.startswith("https://i.chaoxing.com"):
                    await session.page.goto(course_url, wait_until="domcontentloaded", timeout=30_000)

                await asyncio.sleep(2)

            await self._set_status(session, STATUS_EXPIRED, "Chaoxing QR login expired.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chaoxing auth polling failed. sessionId=%s reason=%s", session.session_id, exc)
            await self._set_status(session, STATUS_FAILED, "Chaoxing authorization failed.")
        finally:
            if session.status != STATUS_AUTHORIZED:
                await self._close_runtime(session)

    async def _set_status(self, session: _RuntimeSession, status: str, message: str | None = None) -> None:
        session.status = status
        session.message = message
        await self._store.save_public_state(session)

    def _public_payload(self, session: _RuntimeSession) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "status": session.status,
            "qr_code_url": f"/python/v1/chaoxing/auth/sessions/{session.session_id}/qrcode",
            "message": session.message,
            "expires_at": _iso(session.expires_at),
            "authorized_at": _iso(session.authorized_at),
        }

    @staticmethod
    async def _close_runtime(session: _RuntimeSession) -> None:
        try:
            if session.context is not None:
                await session.context.close()
            if session.browser is not None:
                await session.browser.close()
            if session.playwright is not None:
                await session.playwright.stop()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ignoring Chaoxing auth runtime close failure. sessionId=%s reason=%s", session.session_id, exc)


async def _capture_qr_code(page: Page) -> bytes:
    selectors = ("img", "canvas")
    for selector in selectors:
        elements = await page.locator(selector).all()
        for element in elements:
            try:
                if not await element.is_visible():
                    continue
                box = await element.bounding_box()
                if not box or box.get("width", 0) < 100 or box.get("height", 0) < 100:
                    continue
                return await element.screenshot(type="png")
            except Exception:  # noqa: BLE001
                continue

    # Fallback: return the visible page. This is less precise but keeps the login usable
    # when Chaoxing changes QR markup.
    return await page.screenshot(type="png", full_page=False)


def _is_authorized_cookie_set(cookies: list[dict[str, Any]]) -> bool:
    names = {str(item.get("name", "")) for item in cookies}
    return bool(_COOKIE_NAMES_REQUIRED <= names and names.intersection(_COOKIE_NAMES_SECONDARY))


def _build_cookie_header(cookies: list[dict[str, Any]]) -> str:
    pairs: list[str] = []
    for cookie in cookies:
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "")
        domain = str(cookie.get("domain") or "")
        if not name or "chaoxing.com" not in domain:
            continue
        pairs.append(f"{name}={value}")
    if not pairs:
        raise UnauthorizedFetchError("No Chaoxing cookie was captured.")
    return "; ".join(pairs)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


chaoxing_auth_service = ChaoxingAuthService()
