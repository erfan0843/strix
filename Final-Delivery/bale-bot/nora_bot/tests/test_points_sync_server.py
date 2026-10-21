"""همگام‌سازی واقعی ربات → سرور مشترک، در همین فرایند (بدون شبکه، بدون بله).

سرور FastAPI با پایگاه SQLite حافظه‌ای بالا می‌آید و ``shared_api._request_json``
به ``TestClient`` همان سرور وصل می‌شود؛ پس payload واقعی ربات، اعتبارسنجی واقعی
سرور و وضعیت‌های pending/mirrored/unmapped/failed با هم آزموده می‌شوند.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _points_fixture import ensure_test_env  # noqa: E402

ensure_test_env()

import database  # noqa: E402
import points_ledger as pl  # noqa: E402
import shared_api  # noqa: E402

NORA_UI = ROOT.parents[1] / "website" / "nora-ui"
if str(NORA_UI) not in sys.path:
    sys.path.insert(0, str(NORA_UI))
BACKEND_TESTS = NORA_UI / "backend" / "tests"
if str(BACKEND_TESTS) not in sys.path:
    sys.path.insert(0, str(BACKEND_TESTS))

try:
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from backend.app import create_app
    from backend.config import Settings
    from backend.models import Base, ClubPointsEntryRecord
    from backend.security import hash_password
    from test_workflows_api import BOT_TOKEN, SERVICE_TOKEN, bale_login, owner_login
except Exception as exc:  # pragma: no cover - فقط وقتی سرور در این محیط در دسترس نیست
    pytest.skip(f"backend import unavailable: {type(exc).__name__}", allow_module_level=True)

U_LINKED = 910001
U_UNLINKED = 910777


@pytest.fixture()
def server():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None, owner_id="owner-01", owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"), cookie_secure=False,
        bale_bot_token=BOT_TOKEN, bot_service_token=SERVICE_TOKEN, owner_bale_user_id="70001",
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


@pytest.fixture()
def bot_db(tmp_path, monkeypatch):
    database.close_db()
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "bot.db"))
    database._conn = None
    database.init_db()
    for uid in (U_LINKED, U_UNLINKED):
        database.db_execute("INSERT INTO users (bale_user_id, first_name) VALUES (?, ?)", (uid, f"u{uid}"))
    yield
    database.close_db()


def _bridge(monkeypatch, client, *, outages: list[int]):
    """shared_api._request_json → همان سرور در فرایند؛ با امکان شبیه‌سازی قطعی."""
    calls = {"n": 0}

    def fake_request(method, path, *, payload=None, params=None):
        calls["n"] += 1
        if outages:
            outages.pop(0)
            raise shared_api.SharedAPIError(0, "shared_api_unreachable")
        response = client.request(method, path, json=payload, params=params,
                                  headers={"Authorization": f"Bearer {SERVICE_TOKEN}"})
        if response.status_code >= 400:
            detail = response.json().get("detail") if response.headers.get("content-type", "").startswith("application/json") else None
            raise shared_api.SharedAPIError(response.status_code, str(detail or "shared_api_error"))
        return response.json()

    monkeypatch.setattr(shared_api, "_request_json", fake_request)
    import config

    monkeypatch.setattr(config, "SHARED_API_URL", "http://shared-api.test")
    return calls


def test_real_payload_reaches_real_server_once(server, bot_db, monkeypatch):
    client, engine = server
    linked_account = bale_login(client, U_LINKED)
    client.cookies.clear()
    calls = _bridge(monkeypatch, client, outages=[1])

    e1 = pl.post_points(U_LINKED, 10, entry_type="award", source="achievement", ref_key=f"ach:{U_LINKED}:first",
                        ref_table="user_achievements", ref_id=1)
    e2 = pl.post_points(U_LINKED, -4, entry_type="spend", source="reward_redeem", ref_key="redeem:1",
                        actor_kind="user", ref_table="reward_redemptions", ref_id=1)
    e3 = pl.post_points(U_UNLINKED, 7, entry_type="award", source="achievement", ref_key=f"ach:{U_UNLINKED}:first",
                        ref_table="user_achievements", ref_id=2)

    # قطعی شبکه → failed، بدون ردیف سرور؛ تلاش بعدی → mirrored
    assert pl.sync_entry(e1.entry_id)["outcome"] == "failed"
    with Session(engine) as db:
        assert db.scalar(select(func.count(ClubPointsEntryRecord.id))) == 0
    assert pl.sync_entry(e1.entry_id)["outcome"] == "mirrored"
    assert pl.sync_entry(e2.entry_id)["outcome"] == "mirrored"
    # کاربر بدون هویت سرور → unmapped؛ هیچ حسابی سمت سرور ساخته نمی‌شود
    assert pl.sync_entry(e3.entry_id)["outcome"] == "unmapped"
    before = calls["n"]
    # تکرار: ردیف mirrored بدون درخواست تازه؛ unmapped فقط با include_unmapped دوباره می‌رود
    assert pl.sync_pending()["mirrored"] == 0 and calls["n"] == before
    assert pl.sync_pending(include_unmapped=True)["unmapped"] == 1

    # اگر وضعیت محلی به هر دلیل pending بماند، ارسال دوباره همان کلید ردیف دوم نمی‌سازد
    database.db_execute("UPDATE points_ledger SET shared_status='pending' WHERE id=?", (e1.entry_id,))
    assert pl.sync_entry(e1.entry_id)["outcome"] == "mirrored"
    with Session(engine) as db:
        rows = db.scalars(select(ClubPointsEntryRecord).order_by(ClubPointsEntryRecord.ledger_id)).all()
        assert [(r.ledger_id, r.delta, r.balance_after, r.entry_type, r.account_id) for r in rows] == [
            (e1.entry_id, 10, 10, "award", linked_account),
            (e2.entry_id, -4, 6, "spend", linked_account),
        ]
        assert rows[0].external_key.endswith(f":{e1.entry_id}")
        assert rows[1].actor_kind == "user" and rows[1].ref_key == "redeem:1"
    local = pl.get_entry(e1.entry_id)
    assert local["shared_status"] == "mirrored" and local["shared_entry_id"] == rows[0].id

    # پس از پیوند حساب، ردیف unmapped با همان کلید فقط یک‌بار آینه می‌شود
    bale_login(client, U_UNLINKED)
    client.cookies.clear()
    assert pl.sync_pending(include_unmapped=True)["mirrored"] == 1
    assert pl.sync_pending(include_unmapped=True) == {"mirrored": 0, "unmapped": 0, "failed": 0, "skipped": 0}
    with Session(engine) as db:
        assert db.scalar(select(func.count(ClubPointsEntryRecord.id))) == 3

    # برگشت (reversal) هم با ارجاع به کلید ردیف اصلی آینه می‌شود
    rev = pl.reverse_entry(e2.entry_id, reason="رد درخواست در آزمون", actor_id=1)
    assert pl.sync_entry(rev.entry_id)["outcome"] == "mirrored"
    with Session(engine) as db:
        mirrored = db.scalar(select(ClubPointsEntryRecord).where(ClubPointsEntryRecord.ledger_id == rev.entry_id))
        assert mirrored.entry_type == "reversal" and mirrored.reverses_external_key == rows[1].external_key
        assert mirrored.balance_after == 10

    # پنل همان را می‌بیند: تاریخچهٔ کامل برای کاربر پیوندشده، بدون هیچ مسیر نوشتن
    owner_login(client)
    members = client.get("/api/admin/club/points/members").json()
    by_account = {m["account_id"]: m for m in members["items"]}
    assert by_account[linked_account]["latest_balance"] == 10
    assert by_account[linked_account]["history_complete"] is True
    assert members["write_routes"] is False
    assert pl.reconcile()["sync"] == {"pending": 0, "mirrored": 4, "unmapped": 0, "failed": 0}


def test_shared_api_client_validates_before_any_request(monkeypatch):
    called = []
    monkeypatch.setattr(shared_api, "_request_json", lambda *a, **k: called.append(a) or {"id": "x", "created": True})
    with pytest.raises(shared_api.SharedAPIError) as ei:
        shared_api.submit_points_entry("910001", "k:1", {"ledger_id": 1})
    assert ei.value.code == "invalid_external_key" and not called
    with pytest.raises(shared_api.SharedAPIError):
        shared_api.submit_points_entry("abc", "0c7f7f5e-9c1e-4a7e-8a1c-2b3d4e5f6a7b:1", {"ledger_id": 1})
    with pytest.raises(shared_api.SharedAPIError) as ei:
        shared_api.submit_points_entry("910001", "0c7f7f5e-9c1e-4a7e-8a1c-2b3d4e5f6a7b:1", {})
    assert ei.value.code == "invalid_points_entry" and not called
    # پاسخ نامعتبر سرور → خطای ۵۰۲ (ردیف محلی failed می‌ماند و قابل تکرار است)
    with pytest.raises(shared_api.SharedAPIError) as ei:
        shared_api.submit_points_entry("910001", "0c7f7f5e-9c1e-4a7e-8a1c-2b3d4e5f6a7b:1", {"ledger_id": 1})
    assert ei.value.code == "shared_api_invalid_points_entry" and len(called) == 1
