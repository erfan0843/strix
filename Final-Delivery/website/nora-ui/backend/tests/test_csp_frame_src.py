"""Phase 9.4 §5: opt-in CSP ``frame-src`` allowlist for the external video embeds.

Default is OFF (no header, nothing changes for production). When ``NORA_CSP_FRAME_SRC`` is set the
policy goes out as Report-Only first; enforcement needs an explicit ``NORA_CSP_REPORT_ONLY=0``.
Only HTML pages get the directive — API JSON and the sandboxed file responses keep their own CSP.
Real-browser verification against youtube-nocookie.com / aparat.com is NOT possible in this
repository (no outbound internet) and stays «آزموده‌نشده»; this file proves the header contract only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

from backend import config as config_mod  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import Base  # noqa: E402
from backend.security import hash_password  # noqa: E402

ALLOWLIST = "'self' https://www.youtube-nocookie.com https://www.aparat.com"


def csp_app(**overrides):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None, owner_id="owner-01", owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"), cookie_secure=False, **overrides,
    )
    return create_app(settings, engine=engine), engine


def test_default_sends_no_frame_src_anywhere():
    app, engine = csp_app()
    try:
        with TestClient(app) as client:
            for path in ("/", "/events.html", "/account.html", "/admin.html", "/api/account/certificates"):
                response = client.get(path)
                assert "frame-src" not in response.headers.get("Content-Security-Policy", ""), path
                assert "Content-Security-Policy-Report-Only" not in response.headers, path
                assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    finally:
        engine.dispose()


def test_report_only_is_the_default_when_an_allowlist_is_set():
    app, engine = csp_app(csp_frame_src=ALLOWLIST)
    try:
        with TestClient(app) as client:
            page = client.get("/events.html")
            assert page.status_code == 200 and "text/html" in page.headers["content-type"]
            assert page.headers["Content-Security-Policy-Report-Only"] == f"frame-src {ALLOWLIST}; report-uri /api/csp-report"
            assert "frame-src" not in page.headers.get("Content-Security-Policy", "")
            assert page.headers.get("X-Frame-Options") == "SAMEORIGIN"  # clickjacking protection untouched
            api = client.get("/api/account/certificates")
            assert "Content-Security-Policy-Report-Only" not in api.headers  # JSON never gets frame-src
    finally:
        engine.dispose()


def test_enforced_mode_only_with_explicit_flag_and_never_touches_file_sandbox():
    app, engine = csp_app(csp_frame_src=ALLOWLIST, csp_report_only=False)
    try:
        with TestClient(app) as client:
            page = client.get("/account.html")
            assert page.headers["Content-Security-Policy"] == f"frame-src {ALLOWLIST}; report-uri /api/csp-report"
            assert "Content-Security-Policy-Report-Only" not in page.headers
            # A file-type response keeps its own strict CSP (sandbox) — frame-src is not appended to non-HTML.
            robots = client.get("/robots.txt")
            assert "frame-src" not in robots.headers.get("Content-Security-Policy", "")
    finally:
        engine.dispose()


def test_env_parsing_accepts_only_https_origins_and_self(monkeypatch):
    monkeypatch.setenv("NORA_CSP_FRAME_SRC", " 'self'  https://www.youtube-nocookie.com https://www.aparat.com https://www.aparat.com ")
    assert config_mod._csp_frame_src_env() == ALLOWLIST
    monkeypatch.setenv("NORA_CSP_FRAME_SRC", "")
    assert config_mod._csp_frame_src_env() == ""
    for bad in ("http://www.aparat.com", "https://www.aparat.com/video", "*", "https://*.youtube.com",
                "'self'; script-src 'unsafe-inline'", "javascript:alert(1)", "https://aparat.com\r\nX: y"):
        monkeypatch.setenv("NORA_CSP_FRAME_SRC", bad)
        with pytest.raises(ValueError):
            config_mod._csp_frame_src_env()


def test_csp_report_sink_logs_a_pii_free_summary_and_stores_nothing(caplog):
    """Phase 9.6 §8: the browser posts violations here; only directive + blocked origin + document path reach the log."""
    import logging

    app, engine = csp_app(csp_frame_src=ALLOWLIST)
    try:
        with TestClient(app) as client:
            legacy = {"csp-report": {
                "document-uri": "https://nora.example/event.html?id=ev-1&session=SECRET-TOKEN",
                "effective-directive": "frame-src", "violated-directive": "frame-src",
                "blocked-uri": "https://player.vimeo.com/video/123?h=private-hash", "disposition": "report",
                "original-policy": "frame-src 'self'"}}
            with caplog.at_level(logging.WARNING, logger="nora.csp"):
                response = client.post("/api/csp-report", content=json.dumps(legacy), headers={"Content-Type": "application/csp-report"})
                assert response.status_code == 204 and response.content == b""
                modern = [{"type": "csp-violation", "age": 3, "body": {
                    "documentURL": "https://nora.example/account.html?tab=x", "effectiveDirective": "frame-src",
                    "blockedURL": "https://www.youtube.com/embed/abc?autoplay=1", "disposition": "enforce"}}]
                assert client.post("/api/csp-report", content=json.dumps(modern), headers={"Content-Type": "application/reports+json"}).status_code == 204
            lines = [record.getMessage() for record in caplog.records if record.name == "nora.csp"]
            assert len(lines) == 2 and all(line.startswith("csp_violation ") for line in lines)
            first, second = (json.loads(line.split(" ", 1)[1]) for line in lines)
            assert first == {"directive": "frame-src", "blocked": "https://player.vimeo.com", "document": "/event.html", "disposition": "report"}
            assert second == {"directive": "frame-src", "blocked": "https://www.youtube.com", "document": "/account.html", "disposition": "enforce"}
            joined = "\n".join(lines)
            assert "SECRET-TOKEN" not in joined and "private-hash" not in joined and "autoplay" not in joined
            # Garbage, wrong shapes and oversize bodies are refused without logging; nothing is persisted anywhere.
            assert client.post("/api/csp-report", content=b"not json", headers={"Content-Type": "application/csp-report"}).status_code == 400
            assert client.post("/api/csp-report", content=json.dumps({"hello": 1}), headers={"Content-Type": "application/json"}).status_code == 400
            assert client.post("/api/csp-report", content=b"x" * (16 * 1024 + 1), headers={"Content-Type": "application/csp-report"}).status_code == 413
            assert client.get("/api/csp-report").status_code in {404, 405}  # no read side: nothing is stored
    finally:
        engine.dispose()
