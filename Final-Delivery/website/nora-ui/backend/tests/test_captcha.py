"""Tests for the stateless login captcha (issue, verify, and endpoint wiring)."""
from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path


import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image

from backend.captcha import (
    CAPTCHA_HEIGHT,
    CAPTCHA_IMAGE_PREFIX,
    CAPTCHA_TTL_SECONDS,
    CAPTCHA_WIDTH,
    CaptchaError,
    captcha_nonce,
    issue_captcha,
    verify_captcha,
)
from test_phone_otp_auth import (  # type: ignore[import-not-found]
    ORIGIN,
    PHONE,
    SAFIR_KEY,
    make_client,
    solve_captcha,
)

PEPPER = "captcha-test-pepper-0123456789"


def recover(token: str, pepper: str = PEPPER, now: float = 1001) -> str:
    for number in range(10000):
        answer = f"{number:04d}"
        if verify_captcha(pepper, token, answer, now=now):
            return answer
    raise AssertionError("no answer verified")


def test_issue_requires_pepper_and_returns_png_without_plain_code():
    with pytest.raises(CaptchaError):
        issue_captcha("")
    issued = issue_captcha(PEPPER, now=1000)
    assert issued["expires_in"] == CAPTCHA_TTL_SECONDS
    assert set(issued) == {"token", "image", "expires_in"}
    assert issued["image"].startswith(CAPTCHA_IMAGE_PREFIX)
    raw = base64.b64decode(issued["image"][len(CAPTCHA_IMAGE_PREFIX):], validate=True)
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    picture = Image.open(io.BytesIO(raw))
    assert picture.format == "PNG" and picture.size == (CAPTCHA_WIDTH, CAPTCHA_HEIGHT)
    code = recover(issued["token"], now=1001)
    # پاسخ نه در payload، نه در توکن و نه در متادیتای تصویر به‌صورت متن وجود ندارد؛ فقط پیکسل است.
    assert "<" not in issued["image"] and code not in issued["image"]
    assert code not in issued["token"]
    assert code.encode("ascii") not in raw
    assert not picture.info and not getattr(picture, "text", {})
    assert captcha_nonce(issued["token"]) == json.loads(
        base64.urlsafe_b64decode(issued["token"].split(".", 1)[0] + "==").decode("utf-8")
    )["n"]
    assert captcha_nonce(None) is None and captcha_nonce("not-a-token") is None and captcha_nonce("x" * 600) is None


def test_only_the_issued_code_verifies_and_wrong_answers_fail():
    issued = issue_captcha(PEPPER, now=1000)
    code = recover(issued["token"], now=1001)
    assert verify_captcha(PEPPER, issued["token"], code, now=1001)
    wrong = "0000" if code != "0000" else "1111"
    assert not verify_captcha(PEPPER, issued["token"], wrong, now=1001)
    assert not verify_captcha(PEPPER, issued["token"], "12345", now=1001)
    assert not verify_captcha(PEPPER, issued["token"], "12a4", now=1001)


def test_expired_tampered_and_foreign_tokens_are_rejected():
    issued = issue_captcha(PEPPER, now=1000)
    code = recover(issued["token"], now=1001)
    assert not verify_captcha(PEPPER, issued["token"], code, now=1000 + CAPTCHA_TTL_SECONDS + 5)
    assert not verify_captcha("another-pepper-value-xyz", issued["token"], code, now=1001)
    body, mac = issued["token"].split(".", 1)
    tampered = body + "." + ("0" if mac[0] != "0" else "1") + mac[1:]
    assert not verify_captcha(PEPPER, tampered, code, now=1001)
    assert not verify_captcha(PEPPER, None, code, now=1001)
    assert not verify_captcha(PEPPER, issued["token"] * 200, code, now=1001)


def test_endpoint_issues_no_store_captcha_and_phone_request_needs_a_valid_answer(monkeypatch):
    client, engine, sends = make_client(monkeypatch=monkeypatch)
    try:
        issued = client.get("/api/auth/captcha")
        assert issued.status_code == 200
        assert issued.headers.get("cache-control") == "no-store"
        assert issued.json()["image"].startswith(CAPTCHA_IMAGE_PREFIX)

        token, answer = solve_captcha(client)
        wrong_answer = "0000" if answer != "0000" else "1111"
        wrong = client.post(
            "/api/auth/phone-otp/request",
            json={"phone": PHONE, "captcha_token": token, "captcha_answer": wrong_answer},
            headers=ORIGIN,
        )
        assert wrong.status_code == 422
        assert wrong.json()["detail"] == "invalid_captcha"
        assert sends == []

        missing = client.post("/api/auth/phone-otp/request", json={"phone": PHONE}, headers=ORIGIN)
        assert missing.status_code == 400
    finally:
        engine.dispose()


def test_a_solved_captcha_is_accepted_once_and_then_rejected(monkeypatch):
    client, engine, sends = make_client(monkeypatch=monkeypatch)
    try:
        token, answer = solve_captcha(client)
        body = {"phone": PHONE, "captcha_token": token, "captcha_answer": answer}
        first = client.post("/api/auth/phone-otp/request", json=body, headers=ORIGIN)
        assert first.status_code == 200 and first.json()["accepted"] is True
        assert len(sends) == 1

        replay = client.post("/api/auth/phone-otp/request", json=body, headers=ORIGIN)
        assert replay.status_code == 422
        assert replay.json()["detail"] == "invalid_captcha"
        assert len(sends) == 1

        # همان کپچا برای شمارهٔ دیگر هم قابل استفادهٔ مجدد نیست.
        other = client.post(
            "/api/auth/phone-otp/request",
            json={"phone": "09121111111", "captcha_token": token, "captcha_answer": answer},
            headers=ORIGIN,
        )
        assert other.status_code == 422 and other.json()["detail"] == "invalid_captcha"
        assert len(sends) == 1
    finally:
        engine.dispose()
