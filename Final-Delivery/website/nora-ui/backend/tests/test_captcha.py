"""Tests for the stateless login captcha (issue, verify, and endpoint wiring)."""
from __future__ import annotations

import sys
from pathlib import Path


import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.captcha import (
    CAPTCHA_TTL_SECONDS,
    CaptchaError,
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


def test_issue_requires_pepper_and_returns_svg_without_plain_code():
    with pytest.raises(CaptchaError):
        issue_captcha("")
    issued = issue_captcha(PEPPER, now=1000)
    assert issued["expires_in"] == CAPTCHA_TTL_SECONDS
    assert issued["image"].startswith("<svg") and issued["image"].endswith("</svg>")
    code = recover(issued["token"], now=1001)
    assert all(f">{digit}</text>" in issued["image"] for digit in code)


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
        assert issued.json()["image"].startswith("<svg")

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
