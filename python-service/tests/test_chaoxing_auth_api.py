from __future__ import annotations

import pytest

from app.api.v1 import chaoxing_auth as chaoxing_auth_api


class _FakeChaoxingAuthService:
    async def create_session(self, *, course_url: str | None = None, user_agent: str | None = None):
        return {
            "session_id": "cx_auth_test",
            "status": "WAITING_SCAN",
            "qr_code_url": "/python/v1/chaoxing/auth/sessions/cx_auth_test/qrcode",
            "message": f"created for {course_url or 'default'}",
            "expires_at": "2026-06-08T12:00:00Z",
            "authorized_at": None,
        }

    async def get_session(self, session_id: str):
        return {
            "session_id": session_id,
            "status": "AUTHORIZED",
            "qr_code_url": f"/python/v1/chaoxing/auth/sessions/{session_id}/qrcode",
            "message": "authorized",
            "expires_at": "2026-06-08T12:00:00Z",
            "authorized_at": "2026-06-08T11:55:00Z",
        }

    async def get_qrcode(self, session_id: str):
        assert session_id == "cx_auth_test"
        return b"\x89PNG\r\n\x1a\nfake"

    async def close_session(self, session_id: str):
        return {
            "session_id": session_id,
            "status": "CLOSED",
            "qr_code_url": None,
            "message": "closed",
            "expires_at": None,
            "authorized_at": None,
        }


@pytest.fixture(autouse=True)
def fake_chaoxing_auth_service(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(chaoxing_auth_api, "chaoxing_auth_service", _FakeChaoxingAuthService())


def test_create_chaoxing_auth_session_accepts_camel_case(request_app):
    response = request_app(
        "POST",
        "/python/v1/chaoxing/auth/sessions",
        json={
            "courseUrl": "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
            "userAgent": "test-agent",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["session_id"] == "cx_auth_test"
    assert body["data"]["status"] == "WAITING_SCAN"


def test_get_chaoxing_auth_session_returns_public_state(request_app):
    response = request_app("GET", "/python/v1/chaoxing/auth/sessions/cx_auth_test")

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["status"] == "AUTHORIZED"
    assert "cookie" not in body["data"]


def test_get_chaoxing_auth_qrcode_returns_png(request_app):
    response = request_app("GET", "/python/v1/chaoxing/auth/sessions/cx_auth_test/qrcode")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    assert "no-store" in response.headers["cache-control"]


def test_close_chaoxing_auth_session(request_app):
    response = request_app("DELETE", "/python/v1/chaoxing/auth/sessions/cx_auth_test")

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["status"] == "CLOSED"
