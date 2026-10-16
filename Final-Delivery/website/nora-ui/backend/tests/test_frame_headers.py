"""Framing policy: production keeps SAMEORIGIN; only an explicit dev preview setting changes it."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_phone_otp_auth import make_client  # noqa: E402


def test_default_keeps_same_origin_framing(monkeypatch):
    monkeypatch.delenv("NORA_FRAME_ANCESTORS", raising=False)
    client, engine, _ = make_client(monkeypatch=monkeypatch)
    try:
        response = client.get("/login.html")
        assert response.headers.get("x-frame-options") == "SAMEORIGIN"
        assert "content-security-policy" not in response.headers
    finally:
        engine.dispose()


def test_preview_setting_allows_listed_parents_only(monkeypatch):
    monkeypatch.setenv("NORA_FRAME_ANCESTORS", "'self' https:")
    client, engine, _ = make_client(monkeypatch=monkeypatch)
    try:
        response = client.get("/login.html")
        assert response.headers.get("content-security-policy") == "frame-ancestors 'self' https:"
        assert "x-frame-options" not in response.headers
    finally:
        engine.dispose()


def test_injection_attempt_in_setting_is_ignored(monkeypatch):
    monkeypatch.setenv("NORA_FRAME_ANCESTORS", "https: ; script-src *")
    client, engine, _ = make_client(monkeypatch=monkeypatch)
    try:
        response = client.get("/login.html")
        assert response.headers.get("x-frame-options") == "SAMEORIGIN"
        assert "content-security-policy" not in response.headers
    finally:
        engine.dispose()
