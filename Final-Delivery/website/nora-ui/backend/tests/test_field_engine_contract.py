"""قرارداد موتور فیلدها (فاز اصلاح شکاف‌ها): پذیرش قوانین، ستاره و مقیاس‌ها از انتشار تا پاسخ و CSV.

- «پذیرش قوانین» سروری است: اجباری‌بودن با کلید همین فیلد، پاسخ «پذیرفتم» ذخیره و در CSV دیده می‌شود، «نه» رد می‌شود.
- ستاره: بازهٔ سفارشی (۲ تا ۴)، بازهٔ تک‌مقداری (۳ تا ۳) قابل انتشار است، مقدار خارج از بازه و کسری (۲٫۵) رد می‌شود.
- مقیاس/نوار: فقط عدد صحیح در بازه.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import Base  # noqa: E402
from backend.security import hash_password  # noqa: E402

ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def client():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None, owner_id="owner-01", owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"), session_ttl_seconds=3600, cookie_secure=False,
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def owner_login(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "nora-owner", "password": "correct-horse-staple-42"}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    return {**ORIGIN, "X-CSRF-Token": client.cookies.get("nora_csrf", "")}


def publish_form(client: TestClient, fields: list[dict], key: str) -> str:
    headers = owner_login(client)
    payload = {
        "name": "قرارداد فیلدها " + key, "model": "registration", "need": "reg", "slug": "field-engine/" + key, "ev": "",
        "settings": {"description": "فرم آزمایشی قرارداد فیلدها"}, "fields": fields,
    }
    created = client.post("/api/forms", json=payload, headers={**headers, "Idempotency-Key": "field-engine-" + key})
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    readiness = client.get(f"/api/forms/{form_id}/readiness")
    assert readiness.status_code == 200 and readiness.json()["publishable"] is True, readiness.text
    assert client.post(f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=headers).status_code == 200
    return form_id


def visitor(client: TestClient, form_id: str) -> TestClient:
    public = TestClient(client.app)
    assert public.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    return public


def patch_draft(public: TestClient, form_id: str, answers: dict):
    return public.patch(f"/api/public/forms/{form_id}/draft", json={"answers": answers}, headers=ORIGIN)


def test_terms_is_server_backed_required_enforced_stored_and_exported(client):
    form_id = publish_form(client, [
        {"id": "name", "t": "fullname", "l": "نام"},
        {"id": "rules", "t": "terms", "l": "پذیرش قوانین", "required": True, "help": "متن قوانین برنامه"},
        {"id": "news", "t": "terms", "l": "دریافت خبرنامه", "required": False},
    ], "terms")
    public = visitor(client, form_id)
    # بدون تیک اجباری → ثبت نهایی رد می‌شود و خطا به همان فیلد اشاره می‌کند
    rejected = public.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"name": "سارا"}}, headers=ORIGIN)
    assert rejected.status_code == 422, rejected.text
    assert any(error["field_id"] == "rules" for error in rejected.json()["detail"]["errors"])
    # مقدار غیر از پذیرش → رد (پیش‌نویس هم همان اعتبارسنجی را دارد)
    assert patch_draft(public, form_id, {"rules": "نه"}).status_code == 422
    assert patch_draft(public, form_id, {"rules": "پذیرفتم"}).status_code == 200
    accepted = public.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"name": "سارا", "rules": "پذیرفتم"}}, headers=ORIGIN)
    assert accepted.status_code in (200, 201), accepted.text
    # ذخیره‌شده: فیلد اختیاری بدون تیک، خالی می‌ماند و جعل نمی‌شود
    listed = client.get(f"/api/forms/{form_id}/responses")
    assert listed.status_code == 200
    answers = listed.json()["items"][0]["answers"]
    assert answers["rules"] == "پذیرفتم"
    assert answers.get("news", "") in ("", None)
    exported = client.get(f"/api/forms/{form_id}/responses?format=csv")
    assert exported.status_code == 200
    rows = list(csv.reader(io.StringIO(exported.text.lstrip("\ufeff"))))
    header, body = rows[0], rows[1:]
    assert "پذیرش قوانین" in header and body[0][header.index("پذیرش قوانین")] == "پذیرفتم"
    # قرارداد قابلیت‌ها: پذیرش قوانین سروری (با یادداشت «امضا نیست»)، نه «فقط محلی»
    capabilities = client.get("/api/public/forms/capabilities").json()
    assert capabilities["field_types"]["terms"]["status"] in ("server", "limited")
    assert "ثبت می‌شود" in capabilities["field_types"]["terms"]["reason"]


def test_rating_custom_single_and_fractional_values(client):
    form_id = publish_form(client, [
        {"id": "default", "t": "rating", "l": "ستارهٔ پیش‌فرض"},
        {"id": "custom", "t": "rating", "l": "ستارهٔ ۲ تا ۴", "min": 2, "max": 4, "required": True},
        {"id": "single", "t": "rating", "l": "ستارهٔ تک‌مقداری", "min": "۳", "max": "۳"},
        {"id": "nps", "t": "scale", "l": "طیف", "min": 1, "max": 7},
        {"id": "bar", "t": "bars", "l": "نوار", "min": 0, "max": 5},
    ], "rating")
    public = visitor(client, form_id)
    assert patch_draft(public, form_id, {"default": "0"}).status_code == 422
    assert patch_draft(public, form_id, {"default": "6"}).status_code == 422
    assert patch_draft(public, form_id, {"default": "۵"}).status_code == 200, "رقم فارسی داخل بازه"
    for bad in ("1", "5", "2.5", "۲٫۵", "x"):
        assert patch_draft(public, form_id, {"custom": bad}).status_code == 422, bad
    assert patch_draft(public, form_id, {"custom": "3"}).status_code == 200
    assert patch_draft(public, form_id, {"single": "2"}).status_code == 422
    assert patch_draft(public, form_id, {"single": "3"}).status_code == 200
    assert patch_draft(public, form_id, {"nps": "3.5"}).status_code == 422, "طیف فقط عدد صحیح"
    assert patch_draft(public, form_id, {"nps": "8"}).status_code == 422
    assert patch_draft(public, form_id, {"bar": "4.0"}).status_code == 200, "۴٫۰ همان عدد صحیح ۴ است"
    assert patch_draft(public, form_id, {"bar": "6"}).status_code == 422
    submitted = public.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"default": "4", "custom": "3", "single": "3", "nps": "3", "bar": "2"}}, headers=ORIGIN)
    assert submitted.status_code in (200, 201), submitted.text
    answers = client.get(f"/api/forms/{form_id}/responses").json()["items"][0]["answers"]
    assert (answers["default"], answers["custom"], answers["single"]) == ("4", "3", "3")


def test_rating_range_outside_one_to_five_blocks_publish(client):
    headers = owner_login(client)
    created = client.post("/api/forms", json={
        "name": "ستارهٔ نامعتبر", "model": "registration", "need": "reg", "slug": "field-engine/bad-rating", "ev": "",
        "settings": {"description": "x"}, "fields": [{"id": "r", "t": "rating", "l": "ستاره", "min": 0, "max": 7}],
    }, headers={**headers, "Idempotency-Key": "field-engine-bad-rating"})
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    readiness = client.get(f"/api/forms/{form_id}/readiness").json()
    assert readiness["publishable"] is False
    assert any(issue["code"] == "invalid_numeric_range" and issue["field_id"] == "r" for issue in readiness["issues"])
